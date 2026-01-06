#!/usr/bin/env python3
"""
Historical Trading Simulation for ML Training
============================================

Analiza la base de datos histórica /database.db y simula operativas 
para entrenar el sistema ML con cientos de trades realistas.

Database Structure:
- ScannerEvents: Eventos detectados por ticker + timestamp
- OHLCData: Datos OHLC por minuto para cada evento
- DailyTickerData: Float, market cap, avg volume, short float, etc
- Tickers: Lista de tickers procesados

Estrategias simuladas:
- gap_go: Gaps >8% con volumen alto
- macdv_smallcaps: Breakouts en smallcaps con baja volatilidad  
- daily_plays: Setups diarios con momentum moderado
- reversal_play: Oversold bounces en alta volatilidad
"""

import sys
import os
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.ml_strategy_selector import create_ml_strategy_selector, TickerContext

class HistoricalTradingSimulator:
    
    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path
        self.ml_selector = None
        self.conn = None
        
        # Trading simulation parameters
        self.position_size = 500  # Default position size in $
        self.max_loss = -0.05     # 5% max loss
        self.profit_targets = [0.06, 0.10, 0.15]  # 6%, 10%, 15% targets
        
        print("🎯 Historical Trading Simulator for ML Training")
        print("=" * 60)
        
    def connect_database(self):
        """Connect to historical database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"✅ Connected to database: {self.db_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
    
    def initialize_ml_selector(self):
        """Initialize ML strategy selector"""
        try:
            self.ml_selector = create_ml_strategy_selector(
                strategies=['gap_go', 'macdv_smallcaps', 'daily_plays', 'reversal_play'],
                model_path="data/ml_models/historical_trained_selector.json"
            )
            print("✅ ML Strategy Selector initialized")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize ML selector: {e}")
            return False
    
    def get_tradeable_events(self, limit: int = 500) -> List[Dict]:
        """Get events with sufficient OHLC data for simulation"""
        query = """
        SELECT 
            e.id_event,
            e.ticker,
            e.timestamp,
            d.float_shares,
            d.market_cap,
            d.avg_volume,
            d.short_float,
            d.exchange,
            COUNT(o.id_ohlc) as bar_count
        FROM ScannerEvents e
        LEFT JOIN DailyTickerData d ON e.id_event = d.id_event  
        LEFT JOIN OHLCData o ON e.id_event = o.id_event
        WHERE d.float_shares IS NOT NULL 
        AND d.market_cap IS NOT NULL
        AND d.avg_volume IS NOT NULL
        GROUP BY e.id_event
        HAVING bar_count >= 100  -- At least 100 minutes of data
        ORDER BY e.timestamp DESC
        LIMIT ?
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, (limit,))
        events = cursor.fetchall()
        
        event_list = []
        for event in events:
            event_list.append({
                'id_event': event[0],
                'ticker': event[1], 
                'timestamp': event[2],
                'float_shares': event[3],
                'market_cap': event[4],
                'avg_volume': event[5],
                'short_float': event[6],
                'exchange': event[7],
                'bar_count': event[8]
            })
        
        print(f"📊 Found {len(event_list)} tradeable events")
        return event_list
    
    def get_ohlc_data(self, id_event: int) -> pd.DataFrame:
        """Get OHLC data for specific event"""
        query = """
        SELECT date, open, high, low, close, volume
        FROM OHLCData 
        WHERE id_event = ?
        ORDER BY date ASC
        """
        
        df = pd.read_sql_query(query, self.conn, params=(id_event,))
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        return df
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators from OHLC data"""
        if len(df) < 20:
            return None
            
        try:
            # Price metrics
            first_price = df['close'].iloc[0]
            current_price = df['close'].iloc[-1] 
            price_change = (current_price - first_price) / first_price
            
            # Volume metrics  
            avg_volume_10 = df['volume'].tail(10).mean()
            avg_volume_full = df['volume'].mean()
            volume_ratio = df['volume'].iloc[-1] / avg_volume_full if avg_volume_full > 0 else 1.0
            
            # Volatility
            returns = df['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # Annualized
            
            # RSI approximation (simplified)
            gains = returns.where(returns > 0, 0).rolling(14).mean()
            losses = -returns.where(returns < 0, 0).rolling(14).mean()
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs)).iloc[-1] if not np.isnan(rs.iloc[-1]) else 50.0
            
            # Range analysis
            high_low_range = (df['high'].max() - df['low'].min()) / df['close'].iloc[0]
            
            return {
                'first_price': first_price,
                'current_price': current_price,
                'price_change_pct': price_change * 100,
                'avg_volume_10': avg_volume_10,
                'avg_volume_full': avg_volume_full,
                'volume_ratio': volume_ratio,
                'volatility': volatility,
                'rsi': rsi if not np.isnan(rsi) else 50.0,
                'high_low_range_pct': high_low_range * 100,
                'bar_count': len(df)
            }
            
        except Exception as e:
            print(f"⚠️ Failed to calculate indicators: {e}")
            return None
    
    def create_ticker_context(self, event: Dict, indicators: Dict, market_hour: float = 10.0) -> TickerContext:
        """Create TickerContext from event data and indicators"""
        
        # Smallcap classification (market cap < 300M)
        is_smallcap = event['market_cap'] < 300000000 if event['market_cap'] else True
        
        # Float classification (low float < 20M)
        is_low_float = event['float_shares'] < 20000000 if event['float_shares'] else False
        
        context = TickerContext(
            symbol=event['ticker'],
            current_price=indicators['current_price'],
            avg_volume_10=indicators['avg_volume_10'],
            avg_volume_50=indicators['avg_volume_full'],
            volatility_10=indicators['volatility'],
            volatility_50=indicators['volatility'] * 0.8,  # Assume slightly lower long-term vol
            price_change_1h=indicators['price_change_pct'] * 0.3,  # Estimate 1h change
            price_change_4h=indicators['price_change_pct'] * 0.7,  # Estimate 4h change  
            rsi_14=indicators['rsi'],
            volume_ratio_current=indicators['volume_ratio'],
            volume_spike_frequency=min(0.5, indicators['volume_ratio'] / 5.0),
            hour_of_day=market_hour,
            minutes_from_open=int((market_hour - 9.5) * 60),
            is_first_hour=market_hour < 10.5,
            is_last_hour=market_hour > 15.0,
            market_trend=0.1,  # Assume slightly bullish market
            sector_performance=0.05,  # Assume neutral sector
            breakout_success_rate=0.6 if is_low_float else 0.5,
            mean_reversion_tendency=0.7 if is_smallcap else 0.4
        )
        
        return context
    
    def classify_setup_type(self, event: Dict, indicators: Dict) -> str:
        """Classify what type of setup this event represents - IMPROVED BALANCED VERSION"""
        
        price_change = abs(indicators['price_change_pct'])
        volume_ratio = indicators['volume_ratio']
        volatility = indicators['volatility']
        market_cap = event['market_cap'] or 50000000
        float_shares = event['float_shares'] or 20000000
        rsi = indicators['rsi']
        
        # Calculate priority scores for each strategy
        gap_go_score = 0
        reversal_score = 0
        macdv_score = 0
        daily_score = 0
        
        # Gap and Go: Large price moves OR high volume (more flexible)
        if price_change > 6.0:  # Reduced from 8.0
            gap_go_score += 2
        if volume_ratio > 1.5:  # Reduced from 2.0
            gap_go_score += 1
        if volatility > 0.4:  # Added volatility factor
            gap_go_score += 1
        
        # Reversal Play: High volatility OR oversold conditions (more flexible)
        if volatility > 0.5:  # Reduced from 0.8
            reversal_score += 2
        if rsi < 40:  # Relaxed from 35
            reversal_score += 2
        if price_change > 15.0:  # Big moves often reverse
            reversal_score += 1
        
        # MACDV Smallcaps: Smallcap focus with balanced criteria
        if market_cap < 200000000:  # Increased from 100M (more smallcaps)
            macdv_score += 2
        if volatility < 0.7:  # Relaxed from 0.6
            macdv_score += 1
        if volume_ratio > 1.0:  # Reduced from 1.5
            macdv_score += 1
        if float_shares < 50000000:  # Added low float bonus
            macdv_score += 1
        
        # Daily Plays: Stable, moderate setups
        if volatility < 0.4 and volume_ratio < 2.0:
            daily_score += 2
        if 45 <= rsi <= 65:  # Neutral RSI
            daily_score += 1
        if 5.0 <= price_change <= 15.0:  # Moderate moves
            daily_score += 1
        
        # Select strategy with highest score
        scores = {
            'gap_go': gap_go_score,
            'reversal_play': reversal_score,
            'macdv_smallcaps': macdv_score,
            'daily_plays': daily_score
        }
        
        # Find best strategy
        best_strategy = max(scores.keys(), key=lambda s: scores[s])
        
        # If tie, use original logic as tiebreaker
        if scores[best_strategy] == 0:
            return 'daily_plays'  # Safe fallback
            
        return best_strategy
    
    def simulate_trade_outcome(self, strategy: str, event: Dict, indicators: Dict, ohlc_data: pd.DataFrame) -> Dict:
        """Simulate trade outcome based on strategy and market data"""
        
        entry_price = indicators['current_price']
        entry_time = ohlc_data.index[0]
        
        # Strategy-specific entry/exit logic
        if strategy == 'gap_go':
            # Gap and go: Quick scalp, tight stops
            stop_loss = entry_price * 0.97  # 3% stop
            take_profit_1 = entry_price * 1.06  # 6% target
            max_hold_minutes = 120  # 2 hours max
            
        elif strategy == 'reversal_play':
            # Reversal: Wider stops, bigger targets
            stop_loss = entry_price * 0.95  # 5% stop  
            take_profit_1 = entry_price * 1.10  # 10% target
            max_hold_minutes = 240  # 4 hours max
            
        elif strategy == 'macdv_smallcaps':
            # MACDV: Moderate risk/reward
            stop_loss = entry_price * 0.96  # 4% stop
            take_profit_1 = entry_price * 1.08  # 8% target  
            max_hold_minutes = 180  # 3 hours max
            
        else:  # daily_plays
            # Daily plays: Conservative approach
            stop_loss = entry_price * 0.98  # 2% stop
            take_profit_1 = entry_price * 1.04  # 4% target
            max_hold_minutes = 90   # 1.5 hours max
        
        # Simulate trade execution through price data
        held_minutes = 0
        for i, (timestamp, row) in enumerate(ohlc_data.iterrows()):
            held_minutes = i + 1
            
            # Check stop loss
            if row['low'] <= stop_loss:
                exit_price = stop_loss
                exit_reason = 'STOP_LOSS'
                break
                
            # Check take profit
            if row['high'] >= take_profit_1:
                exit_price = take_profit_1
                exit_reason = 'TAKE_PROFIT'
                break
                
            # Check max hold time
            if held_minutes >= max_hold_minutes:
                exit_price = row['close']
                exit_reason = 'TIME_EXIT'
                break
        else:
            # End of data
            exit_price = ohlc_data['close'].iloc[-1]
            exit_reason = 'END_OF_DATA'
        
        # Calculate PnL
        shares = int(self.position_size / entry_price)
        pnl = (exit_price - entry_price) * shares
        pnl_pct = (exit_price - entry_price) / entry_price * 100
        
        return {
            'entry_price': entry_price,
            'exit_price': exit_price,
            'shares': shares,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'held_minutes': held_minutes,
            'exit_reason': exit_reason,
            'entry_time': entry_time,
            'successful': pnl > 0
        }
    
    def run_simulation(self, max_events: int = 200):
        """Run full simulation on historical data"""
        
        if not self.connect_database():
            return False
            
        if not self.initialize_ml_selector():
            return False
        
        print(f"\n🎯 Starting simulation on up to {max_events} events...")
        print("-" * 60)
        
        # Get tradeable events
        events = self.get_tradeable_events(limit=max_events)
        
        if not events:
            print("❌ No tradeable events found")
            return False
        
        # Simulation results
        simulation_results = []
        successful_simulations = 0
        total_pnl = 0.0
        strategy_performance = {'gap_go': [], 'macdv_smallcaps': [], 'daily_plays': [], 'reversal_play': []}
        
        for i, event in enumerate(events, 1):
            try:
                print(f"\n📊 [{i}/{len(events)}] Processing {event['ticker']} (Event #{event['id_event']})")
                print(f"   Date: {event['timestamp']}")
                print(f"   Market Cap: ${event['market_cap']:,.0f}" if event['market_cap'] else "   Market Cap: N/A")
                print(f"   Float: {event['float_shares']:,.0f}" if event['float_shares'] else "   Float: N/A")
                
                # Get OHLC data
                ohlc_data = self.get_ohlc_data(event['id_event'])
                if len(ohlc_data) < 50:
                    print(f"   ⚠️ Insufficient data ({len(ohlc_data)} bars)")
                    continue
                
                # Calculate indicators
                indicators = self.calculate_technical_indicators(ohlc_data)
                if not indicators:
                    print(f"   ⚠️ Failed to calculate indicators")
                    continue
                
                print(f"   Price Change: {indicators['price_change_pct']:+.1f}%")
                print(f"   Volume Ratio: {indicators['volume_ratio']:.1f}x")
                print(f"   Volatility: {indicators['volatility']:.1%}")
                print(f"   RSI: {indicators['rsi']:.1f}")
                
                # Classify setup and create context
                strategy_type = self.classify_setup_type(event, indicators)
                context = self.create_ticker_context(event, indicators)
                
                print(f"   🎯 Classified as: {strategy_type}")
                
                # Simulate trade
                trade_result = self.simulate_trade_outcome(strategy_type, event, indicators, ohlc_data)
                
                print(f"   💰 Trade Result: ${trade_result['pnl']:+.2f} ({trade_result['pnl_pct']:+.1f}%)")
                print(f"   ⏱️ Held: {trade_result['held_minutes']} min, Exit: {trade_result['exit_reason']}")
                
                # Train ML with result
                reward = max(-1.0, min(1.0, trade_result['pnl_pct'] / 10.0))  # Scale to -1,1
                self.ml_selector.update_model(context, strategy_type, reward)
                
                print(f"   🧠 ML Reward: {reward:.3f}")
                
                # Track results
                simulation_results.append({
                    'ticker': event['ticker'],
                    'timestamp': event['timestamp'],
                    'strategy': strategy_type,
                    'pnl': trade_result['pnl'],
                    'pnl_pct': trade_result['pnl_pct'],
                    'successful': trade_result['successful'],
                    'reward': reward
                })
                
                strategy_performance[strategy_type].append(trade_result['pnl_pct'])
                total_pnl += trade_result['pnl']
                
                if trade_result['successful']:
                    successful_simulations += 1
                    
            except Exception as e:
                print(f"   ❌ Error processing {event['ticker']}: {e}")
                continue
        
        # Save trained ML model
        print(f"\n💾 Saving trained ML model...")
        self.ml_selector.save_model("data/ml_models/historical_trained_selector.json")
        
        # Display results
        self.display_simulation_results(simulation_results, strategy_performance, successful_simulations, total_pnl)
        
        self.conn.close()
        return True
    
    def display_simulation_results(self, results: List[Dict], strategy_perf: Dict, 
                                 successful_count: int, total_pnl: float):
        """Display comprehensive simulation results"""
        
        total_trades = len(results)
        win_rate = (successful_count / total_trades * 100) if total_trades > 0 else 0
        
        print(f"\n" + "=" * 60)
        print("📋 SIMULATION RESULTS SUMMARY")
        print("=" * 60)
        
        print(f"📊 Overall Performance:")
        print(f"   Total Simulated Trades: {total_trades}")
        print(f"   Successful Trades: {successful_count}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Total PnL: ${total_pnl:,.2f}")
        print(f"   Average PnL per Trade: ${total_pnl/total_trades:.2f}" if total_trades > 0 else "")
        
        print(f"\n🎯 Strategy Performance:")
        for strategy, pnls in strategy_perf.items():
            if pnls:
                wins = len([p for p in pnls if p > 0])
                avg_pnl = np.mean(pnls)
                print(f"   {strategy:15} {len(pnls):3d} trades | {wins/len(pnls)*100:5.1f}% WR | {avg_pnl:+6.2f}% avg")
        
        # Top performers
        winners = [r for r in results if r['successful']]
        losers = [r for r in results if not r['successful']]
        
        if winners:
            best_trade = max(winners, key=lambda x: x['pnl_pct'])
            print(f"\n🏆 Best Trade: {best_trade['ticker']} ({best_trade['strategy']}) +{best_trade['pnl_pct']:.1f}%")
        
        if losers:
            worst_trade = min(losers, key=lambda x: x['pnl_pct'])  
            print(f"💸 Worst Trade: {worst_trade['ticker']} ({worst_trade['strategy']}) {worst_trade['pnl_pct']:.1f}%")
        
        # Recent performance
        recent_trades = results[-20:] if len(results) >= 20 else results
        recent_wins = len([r for r in recent_trades if r['successful']])
        recent_wr = (recent_wins / len(recent_trades) * 100) if recent_trades else 0
        
        print(f"\n📈 Recent Performance (Last {len(recent_trades)} trades): {recent_wr:.1f}% WR")
        
        print(f"\n✅ ML Model trained on {total_trades} historical simulations!")
        print(f"🎯 Ready for production trading with learned patterns")

def main():
    """Main execution"""
    
    simulator = HistoricalTradingSimulator("database.db")
    
    print("🚀 Starting Historical Trading Simulation for ML Training")
    print("This will analyze your historical database and simulate trades")
    print("to train the ML system with realistic market patterns.")
    
    # Run simulation
    success = simulator.run_simulation(max_events=300)  # Process up to 300 events
    
    if success:
        print(f"\n🎉 Simulation completed successfully!")
        print(f"📁 ML model saved to: data/ml_models/historical_trained_selector.json")
        print(f"🔄 You can now use this trained model in your live trading system")
    else:
        print(f"\n❌ Simulation failed")
        
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)