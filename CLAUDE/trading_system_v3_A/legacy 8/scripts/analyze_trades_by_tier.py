#!/usr/bin/env python3
"""
Analyze trades by tier (A/B/C/D) to measure performance of exponential sizing strategy

Usage:
    python scripts/analyze_trades_by_tier.py
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta

DB_PATH = "trading_data.db"

def analyze_trades_by_tier():
    """Analyze trade performance by tier"""

    conn = sqlite3.connect(DB_PATH)

    # Get all trades with tier data
    query = """
    SELECT
        trade_tier,
        COUNT(*) as num_trades,
        AVG(expected_value_pct) as avg_ev,
        AVG(risk_reward_ratio) as avg_rr,
        AVG(win_probability) as avg_win_prob,
        AVG(adaptive_risk_pct) as avg_risk_pct,
        AVG(quantity * entry_price) as avg_position_size,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
        AVG(pnl) as avg_pnl,
        SUM(pnl) as total_pnl,
        MAX(pnl) as best_trade,
        MIN(pnl) as worst_trade
    FROM trades
    WHERE trade_tier IS NOT NULL
        AND status = 'CLOSED'
    GROUP BY trade_tier
    ORDER BY trade_tier
    """

    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("❌ No closed trades with tier data found")
        print("💡 Trades need to complete before analysis is possible")
        conn.close()
        return

    # Calculate win rate
    df['win_rate'] = (df['winning_trades'] / df['num_trades'] * 100).round(2)

    print("\n" + "="*80)
    print("📊 TRADE PERFORMANCE BY TIER (Exponential Sizing Strategy)")
    print("="*80)
    print()

    for _, row in df.iterrows():
        tier = row['trade_tier']
        tier_emoji = {
            'A': '🌟',
            'B': '💎',
            'C': '✅',
            'D': '⚪'
        }.get(tier, '❓')

        print(f"{tier_emoji} TIER {tier}")
        print(f"   Trades: {int(row['num_trades'])}")
        print(f"   Expected Value: {row['avg_ev']:.2f}%")
        print(f"   Risk:Reward: {row['avg_rr']:.2f}:1")
        print(f"   Win Probability: {row['avg_win_prob']:.1%}")
        print(f"   Avg Risk %: {row['avg_risk_pct']:.2f}%")
        print(f"   Avg Position Size: ${row['avg_position_size']:.2f}")
        print(f"   Win Rate: {row['win_rate']:.1f}% ({int(row['winning_trades'])}W / {int(row['losing_trades'])}L)")
        print(f"   Avg PnL: ${row['avg_pnl']:.2f}")
        print(f"   Total PnL: ${row['total_pnl']:.2f}")
        print(f"   Best Trade: ${row['best_trade']:.2f}")
        print(f"   Worst Trade: ${row['worst_trade']:.2f}")
        print()

    # Overall stats
    print("="*80)
    print(f"📈 OVERALL STATISTICS")
    print("="*80)
    total_trades = df['num_trades'].sum()
    total_pnl = df['total_pnl'].sum()
    avg_position_size = (df['avg_position_size'] * df['num_trades']).sum() / total_trades

    print(f"Total Trades: {int(total_trades)}")
    print(f"Total PnL: ${total_pnl:.2f}")
    print(f"Avg Position Size: ${avg_position_size:.2f}")
    print(f"PnL per Trade: ${total_pnl / total_trades:.2f}")
    print()

    # Recent trades
    recent_query = """
    SELECT
        symbol,
        trade_tier,
        expected_value_pct,
        risk_reward_ratio,
        adaptive_risk_pct,
        quantity,
        entry_price,
        quantity * entry_price as position_size,
        pnl,
        entry_time
    FROM trades
    WHERE trade_tier IS NOT NULL
    ORDER BY entry_time DESC
    LIMIT 10
    """

    recent_df = pd.read_sql_query(recent_query, conn)

    if not recent_df.empty:
        print("="*80)
        print("🕐 RECENT TRADES")
        print("="*80)
        print()

        for _, trade in recent_df.iterrows():
            tier = trade['trade_tier']
            tier_emoji = {
                'A': '🌟',
                'B': '💎',
                'C': '✅',
                'D': '⚪'
            }.get(tier, '❓')

            pnl_emoji = '✅' if pd.notna(trade['pnl']) and trade['pnl'] > 0 else '❌' if pd.notna(trade['pnl']) else '⏳'
            pnl_str = f"${trade['pnl']:.2f}" if pd.notna(trade['pnl']) else "OPEN"

            print(f"{tier_emoji} {trade['symbol']:6s} | Tier {tier} | "
                  f"EV:{trade['expected_value_pct']:5.1f}% | R:R:{trade['risk_reward_ratio']:4.1f} | "
                  f"Risk:{trade['adaptive_risk_pct']*100:4.1f}% | "
                  f"Size:${trade['position_size']:6.0f} | "
                  f"{pnl_emoji} PnL:{pnl_str:>8s}")

    conn.close()
    print()


if __name__ == "__main__":
    analyze_trades_by_tier()
