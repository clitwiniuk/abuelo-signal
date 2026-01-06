#!/usr/bin/env python3
"""
Robustness Test Runner

Runs regression tests for Momentum Breakout and VCP strategies
using an out-of-sample dataset to verify robustness and check for overfitting.
"""

import sys
import os
import asyncio
import logging

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import simulators
from scripts.simulations.simulate_momentum_adaptive import MomentumSimulator
from scripts.simulations.simulate_vcp_pnl import VCPSimulator
from scripts.simulations.simulate_orb_pnl import ORBSimulator
from scripts.simulations.simulate_daily_plays_pnl import DailyPlaysSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_strategy_test(strategy_name, simulator, symbols):
    print("\n" + "="*80)
    print(f"🚀 TESTING {strategy_name} ROBUSTNESS (Out-of-Sample)")
    print("="*80)
    
    simulator.connect()
    all_trades = []
    
    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        try:
            trades = await simulator.simulate_symbol(symbol)
            if trades:
                all_trades.extend(trades)
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            
    print("\n" + "-"*80)
    print(f"📊 {strategy_name} RESULTS")
    print("-"*80)
    
    total_pnl = sum(t['pnl'] for t in all_trades)
    wins = len([t for t in all_trades if t['pnl'] > 0])
    losses = len([t for t in all_trades if t['pnl'] <= 0])
    total_trades = len(all_trades)
    
    print(f"Total Trades: {total_trades}")
    if total_trades > 0:
        win_rate = (wins/total_trades)*100
        avg_pnl = total_pnl/total_trades
        print(f"Win Rate:     {win_rate:.1f}% ({wins}W-{losses}L)")
        print(f"Total P&L:    ${total_pnl:.2f}")
        print(f"Avg P&L:      ${avg_pnl:.2f}")
    else:
        print("No trades generated.")
        
    return all_trades

async def main():
    # Targeted Set: High Morning Volatility (ORB/Momentum Candidates)
    # Selected based on >10% range in first hour (9:30-10:30)
    out_of_sample_symbols = [
        'NUKK', 'VEEE', 'ABVE', 'RR', 'CRCG', 
        'ESPR', 'BTBT', 'DEFT', 'MSTX', 'WRD'
    ]
    
    print(f"🧪 STARTING TARGETED ROBUSTNESS TEST (High Volatility Set)")
    print(f"📅 Symbols: {', '.join(out_of_sample_symbols)}")
    
    # 1. Test Momentum Breakout
    momentum_sim = MomentumSimulator()
    momentum_trades = await run_strategy_test("MOMENTUM BREAKOUT", momentum_sim, out_of_sample_symbols)
    
    # 2. Test VCP Smallcap
    vcp_sim = VCPSimulator()
    vcp_trades = await run_strategy_test("VCP SMALLCAP", vcp_sim, out_of_sample_symbols)

    # 3. Test ORB Strategy
    orb_sim = ORBSimulator()
    orb_trades = await run_strategy_test("ORB STRATEGY", orb_sim, out_of_sample_symbols)

    # 4. Test Daily Plays
    daily_sim = DailyPlaysSimulator()
    daily_trades = await run_strategy_test("DAILY PLAYS", daily_sim, out_of_sample_symbols)
    
    # Summary
    print("\n" + "="*80)
    print("🏁 FINAL ROBUSTNESS VERIFICATION SUMMARY")
    print("="*80)
    
    print(f"MOMENTUM:    {len(momentum_trades)} trades, ${sum(t['pnl'] for t in momentum_trades):.2f} P&L")
    print(f"VCP:         {len(vcp_trades)} trades, ${sum(t['pnl'] for t in vcp_trades):.2f} P&L")
    print(f"ORB:         {len(orb_trades)} trades, ${sum(t['pnl'] for t in orb_trades):.2f} P&L")
    print(f"DAILY PLAYS: {len(daily_trades)} trades, ${sum(t['pnl'] for t in daily_trades):.2f} P&L")

if __name__ == "__main__":
    asyncio.run(main())
