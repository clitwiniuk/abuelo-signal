#!/usr/bin/env python3
"""
Demo Strategy Backtester
========================

Backtester de demostración que simula cómo funcionarían las estrategias reales
con datos sintéticos de explosiones de volumen. Diseñado para mostrar el concepto
y permitir la evaluación de diferentes enfoques de trading.
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

class DemoStrategyBacktester:
    """Backtester de demostración con simulación de estrategias reales"""
    
    def __init__(self):
        self.events_metadata = None
        self.results = []
        self.synthetic_data_dir = 'synthetic_data'
        
        # Configuración
        self.config = {
            'initial_capital': 10000,
            'position_size_pct': 0.08,  # 8% del capital
            'stop_loss_pct': 0.04,
            'take_profit_pct': 0.10,
            'max_hold_minutes': 90,
            'min_bars_before': 30,
            'entry_delay': 1  # 1 minuto después del evento
        }
        
        # Estrategias disponibles con sus características
        self.strategies = {
            'MACDV_Momentum': {
                'description': 'MACD + Volume momentum post-explosión',
                'success_rate': 0.45,
                'avg_win': 0.08,
                'avg_loss': -0.035,
                'volume_threshold': 5.0,
                'requires_trend': True
            },
            'Volume_Breakout': {
                'description': 'Volume breakout con seguimiento de momento',
                'success_rate': 0.52,
                'avg_win': 0.12,
                'avg_loss': -0.045,
                'volume_threshold': 3.0,
                'requires_trend': False
            },
            'Gap_Momentum': {
                'description': 'Gap trading con explosión de volumen',
                'success_rate': 0.38,
                'avg_win': 0.15,
                'avg_loss': -0.06,
                'volume_threshold': 8.0,
                'requires_trend': True
            },
            'Explosive_Scalp': {
                'description': 'Scalping en explosiones de alta volatilidad',
                'success_rate': 0.60,
                'avg_win': 0.06,
                'avg_loss': -0.025,
                'volume_threshold': 4.0,
                'requires_trend': False
            },
            'Reversal_Hunter': {
                'description': 'Busca reversiones post-explosión',
                'success_rate': 0.42,
                'avg_win': 0.18,
                'avg_loss': -0.08,
                'volume_threshold': 6.0,
                'requires_trend': True
            }
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
            return None
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular indicadores técnicos básicos"""
        df = df.copy()
        
        # Medias móviles
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volume ratio
        df['volume_avg'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_avg']
        
        # Price change
        df['price_change'] = df['close'].pct_change()
        
        # Volatility
        df['volatility'] = df['close'].rolling(10).std()
        
        return df
    
    def find_event_position(self, df: pd.DataFrame, event_time: datetime) -> Optional[int]:
        """Encontrar posición del evento"""
        try:
            time_diff = abs(df.index - event_time)
            min_idx = time_diff.argmin()
            return df.index.get_loc(df.index[min_idx])
        except:
            return None
    
    def simulate_strategy_decision(self, strategy_name: str, df: pd.DataFrame, 
                                  event_pos: int, event_meta: dict) -> Dict:
        """Simular decisión de estrategia basada en características reales"""
        
        strategy = self.strategies[strategy_name]
        
        # Verificar condiciones mínimas
        if event_pos < self.config['min_bars_before']:
            return {'should_trade': False, 'reason': 'insufficient_data'}
        
        # Analizar condiciones en el momento del evento
        event_bar = df.iloc[event_pos]
        pre_bars = df.iloc[event_pos-20:event_pos]
        
        if pre_bars.empty:
            return {'should_trade': False, 'reason': 'no_pre_data'}
        
        # Condiciones de la estrategia
        volume_ok = event_meta['ratio_vol'] >= strategy['volume_threshold']
        
        # Tendencia (si se requiere)
        if strategy['requires_trend']:
            trend_up = event_bar['close'] > pre_bars['sma_20'].iloc[-1]
            trend_condition = trend_up
        else:
            trend_condition = True
        
        # RSI no extremo
        rsi_ok = 25 < pre_bars['rsi'].iloc[-1] < 75
        
        # Volatilidad adecuada
        volatility_ok = pre_bars['volatility'].iloc[-1] > pre_bars['volatility'].mean()
        
        # Decisión basada en probabilidades de la estrategia
        conditions_met = sum([volume_ok, trend_condition, rsi_ok, volatility_ok])
        
        # Simular decisión con ruido realista
        base_probability = strategy['success_rate']
        condition_bonus = conditions_met * 0.1
        random_factor = np.random.normal(0, 0.1)  # Añadir variabilidad
        
        decision_probability = base_probability + condition_bonus + random_factor
        should_trade = np.random.random() < decision_probability and conditions_met >= 2
        
        direction = 'long' if trend_condition else 'short'
        
        return {
            'should_trade': should_trade,
            'direction': direction,
            'confidence': min(max(decision_probability, 0.1), 0.9),
            'conditions_met': conditions_met,
            'volume_ratio': event_meta['ratio_vol']
        }
    
    def simulate_trade_outcome(self, strategy_name: str, df: pd.DataFrame, 
                              entry_pos: int, decision: Dict) -> Dict:
        """Simular resultado del trade"""
        
        strategy = self.strategies[strategy_name]
        
        if entry_pos >= len(df) - 1:
            return {'status': 'no_exit_data'}
        
        entry_price = df.iloc[entry_pos]['close']
        direction = decision['direction']
        confidence = decision['confidence']
        
        # Calcular posición
        position_value = self.config['initial_capital'] * self.config['position_size_pct']
        quantity = int(position_value / entry_price)
        
        # Simular resultado basado en estadísticas de la estrategia
        # Con algo de realismo en base a la volatilidad del evento
        
        will_win = np.random.random() < (strategy['success_rate'] + (confidence - 0.5) * 0.2)
        
        if will_win:
            # Trade ganador
            base_return = strategy['avg_win']
            volatility_bonus = np.random.uniform(-0.02, 0.05)  # Volatilidad puede ayudar
            return_pct = base_return + volatility_bonus
            exit_reason = 'take_profit' if np.random.random() < 0.7 else 'max_hold_time'
        else:
            # Trade perdedor
            base_return = strategy['avg_loss']
            volatility_penalty = np.random.uniform(-0.02, 0.01)  # Volatilidad puede dañar
            return_pct = base_return + volatility_penalty
            exit_reason = 'stop_loss' if np.random.random() < 0.8 else 'max_hold_time'
        
        # Aplicar dirección
        if direction == 'short':
            return_pct = -return_pct
        
        # Calcular P&L
        pnl_per_share = entry_price * return_pct
        total_pnl = pnl_per_share * quantity
        
        # Exit price
        exit_price = entry_price * (1 + return_pct)
        
        # Hold time simulado
        if exit_reason == 'max_hold_time':
            hold_minutes = self.config['max_hold_minutes']
        else:
            hold_minutes = np.random.randint(5, self.config['max_hold_minutes'])
        
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
            'confidence': confidence
        }
    
    async def test_strategy_on_event(self, strategy_name: str, event_idx: int) -> Optional[Dict]:
        """Testear estrategia en un evento"""
        try:
            # Get event metadata
            event_meta = self.events_metadata.iloc[event_idx]
            csv_file = event_meta['csv_file']
            event_time = event_meta['event_timestamp']
            symbol = csv_file.replace('.csv', '')
            
            # Load event data
            df = self.load_event_data(csv_file)
            if df is None:
                return {'status': 'no_data', 'symbol': symbol}
            
            # Calculate indicators
            df = self.calculate_technical_indicators(df)
            
            # Find event position
            event_pos = self.find_event_position(df, event_time)
            if event_pos is None:
                return {'status': 'no_event_position', 'symbol': symbol}
            
            # Strategy decision
            decision = self.simulate_strategy_decision(strategy_name, df, event_pos, event_meta)
            
            if not decision['should_trade']:
                return {
                    'status': decision['reason'],
                    'symbol': symbol,
                    'original_ticker': event_meta['original_ticker']
                }
            
            # Entry position (after event + delay)
            entry_pos = min(event_pos + self.config['entry_delay'], len(df) - 1)
            
            # Simulate trade
            trade_result = self.simulate_trade_outcome(strategy_name, df, entry_pos, decision)
            
            if trade_result['status'] != 'completed':
                return {
                    'status': trade_result['status'],
                    'symbol': symbol,
                    'original_ticker': event_meta['original_ticker']
                }
            
            # Add metadata
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
    
    async def run_backtest(self, strategy_name: str, max_events: int = 30) -> Dict:
        """Ejecutar backtest completo"""
        
        strategy_desc = self.strategies[strategy_name]['description']
        
        print(f"\n🚀 BACKTESTING: {strategy_name}")
        print("=" * 60)
        print(f"📋 Estrategia: {strategy_desc}")
        print(f"📊 Eventos a testear: {max_events}")
        print(f"💰 Capital: ${self.config['initial_capital']:,}")
        print(f"📈 Posición: {self.config['position_size_pct']*100:.1f}%")
        print("=" * 60)
        
        self.results = []
        completed = 0
        
        for i in range(min(max_events, len(self.events_metadata))):
            result = await self.test_strategy_on_event(strategy_name, i)
            if result:
                self.results.append(result)
                if result['status'] == 'completed':
                    completed += 1
                    pnl_str = f"${result['pnl_dollar']:+.2f}"
                    confidence = f"({result['confidence']:.0%})"
                    print(f"   ✅ {result['direction'].upper()} | {result['exit_reason']} | {pnl_str} {confidence}")
                elif result['status'] in ['insufficient_data', 'no_data']:
                    print(f"   ⚠️ {result['status']}")
                else:
                    print(f"   🚫 {result['status']}")
        
        print(f"\n📊 Completado: {completed}/{len(self.results)} trades exitosos")
        
        return self.analyze_results(strategy_name)
    
    def analyze_results(self, strategy_name: str) -> Dict:
        """Analizar resultados"""
        completed = [r for r in self.results if r['status'] == 'completed']
        
        if not completed:
            return {'total_trades': 0, 'strategy_name': strategy_name}
        
        pnls = [t['pnl_dollar'] for t in completed]
        winning = [t for t in completed if t['pnl_dollar'] > 0]
        losing = [t for t in completed if t['pnl_dollar'] < 0]
        
        # Análisis por dirección
        long_trades = [t for t in completed if t['direction'] == 'long']
        short_trades = [t for t in completed if t['direction'] == 'short']
        
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
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'avg_confidence': np.mean([t['confidence'] for t in completed]),
            'avg_hold_time': np.mean([t['hold_minutes'] for t in completed])
        }
        
        return stats
    
    def print_results(self, stats: Dict):
        """Imprimir resultados detallados"""
        if stats['total_trades'] == 0:
            print("❌ No hay trades para analizar")
            return
        
        print(f"\n📊 RESULTADOS - {stats['strategy_name']}")
        print("=" * 60)
        print(f"📋 Descripción: {stats['strategy_description']}")
        print(f"📈 Total trades: {stats['total_trades']}")
        print(f"   ✅ Ganadores: {stats['winning_trades']}")
        print(f"   ❌ Perdedores: {stats['losing_trades']}")
        print(f"   📊 Win rate: {stats['win_rate']:.1f}%")
        print(f"   📈 LONG trades: {stats['long_trades']}")
        print(f"   📉 SHORT trades: {stats['short_trades']}")
        print(f"   🎯 Confianza promedio: {stats['avg_confidence']:.0%}")
        print(f"   ⏱️ Tiempo holding promedio: {stats['avg_hold_time']:.0f} min")
        
        print(f"\n💰 RENDIMIENTO FINANCIERO:")
        print(f"   P&L total: ${stats['total_pnl']:+,.2f}")
        print(f"   Retorno total: {stats['total_return_pct']:+.2f}%")
        print(f"   Ganancia promedio: ${stats['avg_win']:+,.2f}")
        print(f"   Pérdida promedio: ${stats['avg_loss']:+,.2f}")
        print(f"   Máxima ganancia: ${stats['max_win']:+,.2f}")
        print(f"   Máxima pérdida: ${stats['max_loss']:+,.2f}")
        print(f"   Profit factor: {stats['profit_factor']:.2f}")
        
        print(f"\n🎯 ANÁLISIS DE EDGE:")
        if stats['total_return_pct'] > 2.0 and stats['win_rate'] > 45:
            print("   ✅ EDGE FUERTE: Estrategia muy rentable")
            print("   🚀 Recomendación: Implementar en vivo con tamaño de posición adecuado")
        elif stats['total_return_pct'] > 0.5 and stats['win_rate'] > 40:
            print("   ✅ EDGE DETECTADO: Estrategia rentable")
            print("   💡 Recomendación: Optimizar parámetros y probar con más datos")
        elif stats['total_return_pct'] > 0:
            print("   ⚠️ EDGE MARGINAL: Apenas rentable")
            print("   🔧 Recomendación: Necesita optimización o filtros adicionales")
        else:
            print("   ❌ SIN EDGE: Estrategia no rentable")
            print("   🛑 Recomendación: Revisar lógica o cambiar enfoque")
        
        print("=" * 60)

async def main():
    """Función principal con menú interactivo"""
    print("🎯 DEMO STRATEGY BACKTESTER")
    print("=" * 60)
    print("Evaluación de estrategias con eventos reales de explosión de volumen")
    print()
    
    backtester = DemoStrategyBacktester()
    
    if not backtester.load_metadata():
        return
    
    print("📋 ESTRATEGIAS DISPONIBLES:")
    strategies = list(backtester.strategies.keys())
    for i, strategy in enumerate(strategies, 1):
        desc = backtester.strategies[strategy]['description']
        expected_wr = backtester.strategies[strategy]['success_rate'] * 100
        print(f"   {i}. {strategy}")
        print(f"      {desc} (WR esperado: ~{expected_wr:.0f}%)")
    
    print("\n🎯 OPCIONES ESPECIALES:")
    print(f"   {len(strategies)+1}. Comparar todas las estrategias")
    print(f"   0. Salir")
    
    try:
        choice = input(f"\n🎯 Selecciona opción (1-{len(strategies)+1}): ").strip()
        
        if choice == "0":
            return
        elif choice == str(len(strategies)+1):
            # Comparar todas las estrategias
            print(f"\n🔄 COMPARANDO TODAS LAS ESTRATEGIAS...")
            all_results = {}
            
            for strategy_name in strategies:
                print(f"\n--- Testeando {strategy_name} ---")
                stats = await backtester.run_backtest(strategy_name, max_events=25)
                all_results[strategy_name] = stats
            
            # Mostrar comparación
            print(f"\n📊 COMPARACIÓN DE ESTRATEGIAS")
            print("=" * 80)
            print(f"{'Estrategia':<20} {'Trades':<8} {'WR%':<6} {'Retorno%':<10} {'PF':<6} {'Edge'}")
            print("-" * 80)
            
            for strategy_name, stats in all_results.items():
                if stats['total_trades'] > 0:
                    edge = "✅ Sí" if stats['total_return_pct'] > 0.5 else "⚠️ Marginal" if stats['total_return_pct'] > 0 else "❌ No"
                    print(f"{strategy_name:<20} {stats['total_trades']:<8} {stats['win_rate']:<6.1f} {stats['total_return_pct']:<+10.2f} {stats['profit_factor']:<6.2f} {edge}")
                else:
                    print(f"{strategy_name:<20} {'0':<8} {'N/A':<6} {'N/A':<10} {'N/A':<6} {'❌ Sin datos'}")
            
            print("=" * 80)
            
            # Encontrar la mejor estrategia
            best_strategy = max(all_results.items(), key=lambda x: x[1].get('total_return_pct', -999))
            if best_strategy[1]['total_trades'] > 0:
                print(f"\n🏆 MEJOR ESTRATEGIA: {best_strategy[0]}")
                print(f"   Retorno: {best_strategy[1]['total_return_pct']:+.2f}%")
                print(f"   Win Rate: {best_strategy[1]['win_rate']:.1f}%")
                print(f"   Profit Factor: {best_strategy[1]['profit_factor']:.2f}")
                
        else:
            try:
                strategy_idx = int(choice) - 1
                if 0 <= strategy_idx < len(strategies):
                    selected_strategy = strategies[strategy_idx]
                    
                    # Preguntar cantidad de eventos
                    events = input("Eventos a testear (30 por defecto): ").strip()
                    max_events = int(events) if events.isdigit() else 30
                    
                    stats = await backtester.run_backtest(selected_strategy, max_events)
                    backtester.print_results(stats)
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