#!/usr/bin/env python3
"""
Simple Real Strategy Backtester
==============================

Backtester simplificado que usa las estrategias REALES del sistema 
para evaluar rendimiento con datos sintéticos de explosiones de volumen.
"""

import pandas as pd
import numpy as np
import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import MarketData, SignalType
from strategies import STRATEGY_REGISTRY
from strategies.macdv_strategy import MACDVStrategy

class SimpleRealBacktester:
    """Backtester simplificado con estrategias reales"""
    
    def __init__(self):
        self.events_metadata = None
        self.results = []
        self.synthetic_data_dir = 'synthetic_data'
        
        # Configuración
        self.config = {
            'initial_capital': 10000,
            'position_size_pct': 0.10,  # 10% del capital
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.12,
            'max_hold_minutes': 120,
            'min_bars_before': 50,
            'entry_delay': 2
        }
    
    def load_metadata(self) -> bool:
        """Cargar metadatos de eventos"""
        try:
            metadata_path = os.path.join(self.synthetic_data_dir, 'events_metadata.csv')
            self.events_metadata = pd.read_csv(metadata_path)
            self.events_metadata['event_timestamp'] = pd.to_datetime(self.events_metadata['event_timestamp'])
            print(f"✅ Metadatos cargados: {len(self.events_metadata)} eventos")
            return True
        except Exception as e:
            print(f"❌ Error cargando metadatos: {e}")
            return False
    
    def load_event_data(self, csv_filename: str) -> Optional[pd.DataFrame]:
        """Cargar datos de un evento"""
        try:
            csv_path = os.path.join(self.synthetic_data_dir, csv_filename)
            df = pd.read_csv(csv_path)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            return df
        except Exception as e:
            print(f"❌ Error cargando {csv_filename}: {e}")
            return None
    
    def create_market_data(self, df: pd.DataFrame, symbol: str) -> List[MarketData]:
        """Convertir DataFrame a MarketData"""
        bars = []
        for timestamp, row in df.iterrows():
            bar = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume']),
                timeframe="1 min"
            )
            bars.append(bar)
        return bars
    
    def find_event_position(self, df: pd.DataFrame, event_time: datetime) -> Optional[int]:
        """Encontrar posición del evento"""
        try:
            time_diff = abs(df.index - event_time)
            min_idx = time_diff.argmin()
            return df.index.get_loc(df.index[min_idx])
        except:
            return None
    
    async def test_strategy_on_event(self, strategy_name: str, event_idx: int) -> Optional[Dict]:
        """Testear estrategia en un evento"""
        try:
            # Get event metadata
            event_meta = self.events_metadata.iloc[event_idx]
            csv_file = event_meta['csv_file']
            event_time = event_meta['event_timestamp']
            symbol = csv_file.replace('.csv', '')
            
            print(f"📊 Testing {symbol} | {event_meta['original_ticker']} | {event_meta['ratio_vol']:.1f}x")
            
            # Load event data
            df = self.load_event_data(csv_file)
            if df is None:
                return None
            
            # Find event position
            event_pos = self.find_event_position(df, event_time)
            if event_pos is None or event_pos < self.config['min_bars_before']:
                return {'status': 'insufficient_data', 'symbol': symbol}
            
            # Create strategy instance
            strategy_params = {
                'max_position_value': 500.0,
                'stop_loss_pct': self.config['stop_loss_pct'],
                'take_profit_pct': self.config['take_profit_pct'],
            }
            
            if strategy_name == 'MACDVStrategy':
                strategy = MACDVStrategy(strategy_params)
            else:
                return {'status': 'strategy_not_supported', 'symbol': symbol}
            
            # Convert to MarketData
            bars = self.create_market_data(df, symbol)
            
            # Process bars up to event + delay
            entry_pos = min(event_pos + self.config['entry_delay'], len(bars) - 1)
            signal = None
            
            # Feed bars to strategy up to entry point
            for i in range(entry_pos + 1):
                signal = await strategy.on_bar(bars[i])
                if signal and signal.signal_type in [SignalType.LONG, SignalType.SHORT]:
                    break
            
            if not signal or signal.signal_type not in [SignalType.LONG, SignalType.SHORT]:
                return {'status': 'no_signal', 'symbol': symbol}
            
            # Execute trade simulation
            entry_bar = bars[entry_pos]
            entry_price = entry_bar.close
            direction = 'long' if signal.signal_type == SignalType.LONG else 'short'
            
            # Calculate position
            position_value = self.config['initial_capital'] * self.config['position_size_pct']
            quantity = int(position_value / entry_price)
            
            if quantity <= 0:
                return {'status': 'invalid_quantity', 'symbol': symbol}
            
            # Set exit levels
            if direction == 'long':
                stop_loss = entry_price * (1 - self.config['stop_loss_pct'])
                take_profit = entry_price * (1 + self.config['take_profit_pct'])
            else:
                stop_loss = entry_price * (1 + self.config['stop_loss_pct'])
                take_profit = entry_price * (1 - self.config['take_profit_pct'])
            
            # Simulate holding
            max_hold_pos = min(entry_pos + self.config['max_hold_minutes'], len(bars) - 1)
            
            for i in range(entry_pos + 1, max_hold_pos + 1):
                current_price = bars[i].close
                
                if direction == 'long':
                    if current_price <= stop_loss:
                        exit_price = stop_loss
                        exit_reason = 'stop_loss'
                        break
                    elif current_price >= take_profit:
                        exit_price = take_profit
                        exit_reason = 'take_profit'
                        break
                else:
                    if current_price >= stop_loss:
                        exit_price = stop_loss
                        exit_reason = 'stop_loss'
                        break
                    elif current_price <= take_profit:
                        exit_price = take_profit
                        exit_reason = 'take_profit'
                        break
            else:
                exit_price = bars[max_hold_pos].close
                exit_reason = 'max_hold_time'
            
            # Calculate P&L
            if direction == 'long':
                pnl_per_share = exit_price - entry_price
            else:
                pnl_per_share = entry_price - exit_price
            
            total_pnl = pnl_per_share * quantity
            pnl_pct = (pnl_per_share / entry_price) * 100
            
            return {
                'status': 'completed',
                'symbol': symbol,
                'original_ticker': event_meta['original_ticker'],
                'strategy': strategy_name,
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'pnl_dollar': total_pnl,
                'pnl_pct': pnl_pct,
                'exit_reason': exit_reason,
                'ratio_vol': event_meta['ratio_vol'],
                'percent_var': event_meta['percent_var']
            }
            
        except Exception as e:
            print(f"❌ Error testing event {event_idx}: {e}")
            return None
    
    async def run_backtest(self, strategy_name: str, max_events: int = 20) -> Dict:
        """Ejecutar backtest completo"""
        print(f"\n🚀 BACKTESTING CON {strategy_name}")
        print("=" * 50)
        print(f"📊 Eventos a testear: {max_events}")
        print(f"💰 Capital: ${self.config['initial_capital']:,}")
        print(f"📈 Posición: {self.config['position_size_pct']*100:.1f}%")
        print("=" * 50)
        
        self.results = []
        completed = 0
        
        for i in range(min(max_events, len(self.events_metadata))):
            result = await self.test_strategy_on_event(strategy_name, i)
            if result:
                self.results.append(result)
                if result['status'] == 'completed':
                    completed += 1
                    pnl_str = f"${result['pnl_dollar']:+.2f}"
                    print(f"   ✅ {result['direction'].upper()} | {result['exit_reason']} | {pnl_str}")
                else:
                    print(f"   ⚠️ {result['status']}")
        
        print(f"\n📊 Completado: {completed}/{len(self.results)} trades exitosos")
        
        return self.analyze_results()
    
    def analyze_results(self) -> Dict:
        """Analizar resultados"""
        completed = [r for r in self.results if r['status'] == 'completed']
        
        if not completed:
            return {'total_trades': 0}
        
        pnls = [t['pnl_dollar'] for t in completed]
        winning = [t for t in completed if t['pnl_dollar'] > 0]
        losing = [t for t in completed if t['pnl_dollar'] < 0]
        
        stats = {
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
            'profit_factor': abs(sum([t['pnl_dollar'] for t in winning]) / sum([t['pnl_dollar'] for t in losing])) if losing else float('inf')
        }
        
        return stats
    
    def print_results(self, stats: Dict):
        """Imprimir resultados"""
        if stats['total_trades'] == 0:
            print("❌ No hay trades para analizar")
            return
        
        print(f"\n📊 RESULTADOS DEL BACKTEST")
        print("=" * 40)
        print(f"Total trades: {stats['total_trades']}")
        print(f"Trades ganadores: {stats['winning_trades']}")
        print(f"Trades perdedores: {stats['losing_trades']}")
        print(f"Win rate: {stats['win_rate']:.1f}%")
        print(f"P&L total: ${stats['total_pnl']:+,.2f}")
        print(f"Retorno: {stats['total_return_pct']:+.2f}%")
        print(f"Ganancia promedio: ${stats['avg_win']:+,.2f}")
        print(f"Pérdida promedio: ${stats['avg_loss']:+,.2f}")
        print(f"Profit factor: {stats['profit_factor']:.2f}")
        print("=" * 40)
        
        if stats['total_return_pct'] > 1.0:
            print("✅ EDGE DETECTADO: Estrategia rentable")
        elif stats['total_return_pct'] > 0:
            print("⚠️ EDGE MARGINAL: Apenas rentable")
        else:
            print("❌ SIN EDGE: Estrategia no rentable")

async def main():
    """Función principal"""
    print("🎯 SIMPLE REAL STRATEGY BACKTESTER")
    print("=" * 50)
    
    backtester = SimpleRealBacktester()
    
    if not backtester.load_metadata():
        return
    
    print("\n📋 ESTRATEGIAS DISPONIBLES:")
    strategies = ['MACDVStrategy']  # Por ahora solo MACDV
    for i, strategy in enumerate(strategies, 1):
        print(f"   {i}. {strategy}")
    
    try:
        choice = input("\n🎯 Selecciona estrategia (1): ").strip() or "1"
        
        if choice == "1":
            strategy = "MACDVStrategy"
        else:
            strategy = "MACDVStrategy"  # Default
        
        print(f"✅ Seleccionada: {strategy}")
        
        # Ejecutar backtest
        stats = await backtester.run_backtest(strategy, max_events=20)
        backtester.print_results(stats)
        
    except KeyboardInterrupt:
        print("\n👋 Cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())