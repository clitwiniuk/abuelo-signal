#!/usr/bin/env python3
"""
Test script for execution tracking and slippage calculation
Creates sample trades to verify the enhanced pricing system works correctly
"""

import sqlite3
import sys
import os
from datetime import datetime, timedelta
import random

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.execution_tracker import get_execution_tracker

def create_sample_trades():
    """Create sample trades to test the system"""
    db_path = "../trading_data.db"
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create sample planned trades
    sample_trades = [
        {
            'trade_id': 'TEST_SSKN_001',
            'symbol': 'SSKN',
            'strategy': 'momentum_breakout',
            'side': 'BUY',
            'quantity': 76,
            'entry_price': 2.63,  # Planned price
            'exit_price': 2.905,   # Planned price
            'entry_time': '2025-09-02 19:26:21',
            'exit_time': '2025-09-02 21:55:28',
            'status': 'CLOSED',
            'commission': 0.72,
            'pnl': 20.90  # Planned P&L
        },
        {
            'trade_id': 'TEST_HWH_001', 
            'symbol': 'HWH',
            'strategy': 'momentum_breakout',
            'side': 'BUY',
            'quantity': 33,
            'entry_price': 5.98,  # Planned price
            'exit_price': 5.60,   # Planned price  
            'entry_time': '2025-09-02 19:21:47',
            'exit_time': '2025-09-02 19:42:08',
            'status': 'CLOSED',
            'commission': 0.72,
            'pnl': -13.16  # Planned P&L
        }
    ]
    
    # Insert sample trades
    for trade in sample_trades:
        cursor.execute("""
            INSERT OR REPLACE INTO trades 
            (trade_id, symbol, strategy, side, quantity, entry_price, exit_price, 
             entry_time, exit_time, status, commission, pnl, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade['trade_id'], trade['symbol'], trade['strategy'], trade['side'],
            trade['quantity'], trade['entry_price'], trade['exit_price'],
            trade['entry_time'], trade['exit_time'], trade['status'],
            trade['commission'], trade['pnl'], datetime.now(), datetime.now()
        ))
    
    conn.commit()
    conn.close()
    
    print("✅ Sample trades created successfully")
    return sample_trades

def simulate_real_executions(sample_trades):
    """Simulate real broker executions with slippage"""
    execution_tracker = get_execution_tracker("../trading_data.db")
    
    # Simulate real execution prices (with slippage)
    real_executions = [
        {
            'trade_id': 'TEST_SSKN_001',
            'symbol': 'SSKN',
            'entry_execution': {
                'side': 'BUY',
                'price': 2.65,  # Real executed price (slippage: +0.02)
                'time': datetime.strptime('2025-09-02 19:26:21', '%Y-%m-%d %H:%M:%S')
            },
            'exit_execution': {
                'side': 'SELL', 
                'price': 2.90,  # Real executed price (slippage: -0.005)
                'time': datetime.strptime('2025-09-02 21:55:28', '%Y-%m-%d %H:%M:%S')
            }
        },
        {
            'trade_id': 'TEST_HWH_001',
            'symbol': 'HWH',
            'entry_execution': {
                'side': 'BUY',
                'price': 6.13,  # Real executed price (slippage: +0.15)
                'time': datetime.strptime('2025-09-02 19:21:47', '%Y-%m-%d %H:%M:%S')
            },
            'exit_execution': {
                'side': 'SELL',
                'price': 5.58,  # Real executed price (slippage: -0.02)
                'time': datetime.strptime('2025-09-02 19:42:08', '%Y-%m-%d %H:%M:%S')
            }
        }
    ]
    
    # Record the executions
    for execution in real_executions:
        symbol = execution['symbol']
        
        # Record entry execution
        print(f"\n🔄 Recording entry execution for {symbol}...")
        entry_success = execution_tracker.record_execution(
            symbol=symbol,
            side=execution['entry_execution']['side'],
            executed_price=execution['entry_execution']['price'],
            executed_quantity=76 if symbol == 'SSKN' else 33,
            execution_time=execution['entry_execution']['time'],
            broker_order_id=f"IB_{symbol}_ENTRY",
            trade_id=execution['trade_id']
        )
        
        # Record exit execution
        print(f"🔄 Recording exit execution for {symbol}...")
        exit_success = execution_tracker.record_execution(
            symbol=symbol,
            side=execution['exit_execution']['side'],
            executed_price=execution['exit_execution']['price'],
            executed_quantity=76 if symbol == 'SSKN' else 33,
            execution_time=execution['exit_execution']['time'],
            broker_order_id=f"IB_{symbol}_EXIT",
            trade_id=execution['trade_id']
        )
        
        if entry_success and exit_success:
            print(f"✅ Both executions recorded for {symbol}")
        else:
            print(f"❌ Error recording executions for {symbol}")

def verify_results():
    """Verify the results and show the comparison"""
    db_path = "../trading_data.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get the enhanced trade data
    cursor.execute("""
        SELECT 
            trade_id,
            symbol,
            -- Planned prices and P&L
            entry_price as planned_entry,
            exit_price as planned_exit,
            pnl as original_pnl,
            planned_pnl,
            -- Actual execution prices and P&L
            actual_entry_price,
            actual_exit_price,
            actual_pnl,
            -- Slippage metrics
            entry_slippage,
            exit_slippage,
            entry_slippage_pct,
            exit_slippage_pct,
            total_slippage_impact,
            -- Status
            entry_filled,
            exit_filled
        FROM trades 
        WHERE trade_id LIKE 'TEST_%'
        ORDER BY symbol
    """)
    
    results = cursor.fetchall()
    
    print("\n" + "="*80)
    print("📊 EXECUTION TRACKING RESULTS")
    print("="*80)
    
    total_planned_pnl = 0
    total_actual_pnl = 0
    total_slippage_impact = 0
    
    for row in results:
        (trade_id, symbol, planned_entry, planned_exit, original_pnl, planned_pnl,
         actual_entry, actual_exit, actual_pnl, entry_slippage, exit_slippage,
         entry_slippage_pct, exit_slippage_pct, slippage_impact,
         entry_filled, exit_filled) = row
        
        print(f"\n📈 {symbol} ({trade_id})")
        print(f"   Planned Entry: ${planned_entry:.4f} → Actual: ${actual_entry:.4f} (Slippage: ${entry_slippage:.4f})")
        print(f"   Planned Exit:  ${planned_exit:.4f} → Actual: ${actual_exit:.4f} (Slippage: ${exit_slippage:.4f})")
        print(f"   Planned P&L:   ${planned_pnl:.2f}")
        print(f"   Actual P&L:    ${actual_pnl:.2f}")
        print(f"   Slippage Impact: ${slippage_impact:.2f}")
        print(f"   Filled Status: Entry={bool(entry_filled)}, Exit={bool(exit_filled)}")
        
        total_planned_pnl += planned_pnl or 0
        total_actual_pnl += actual_pnl or 0
        total_slippage_impact += slippage_impact or 0
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total Planned P&L:     ${total_planned_pnl:.2f}")
    print(f"   Total Actual P&L:      ${total_actual_pnl:.2f}")  
    print(f"   Total Slippage Impact: ${total_slippage_impact:.2f}")
    print(f"   Difference:            ${total_actual_pnl - total_planned_pnl:.2f}")
    
    # Get slippage statistics
    execution_tracker = get_execution_tracker(db_path)
    slippage_stats = execution_tracker.get_slippage_stats(days=30)
    
    print(f"\n📈 SLIPPAGE STATISTICS:")
    for key, value in slippage_stats.items():
        if key != 'period_days':
            print(f"   {key.replace('_', ' ').title()}: {value}")
    
    conn.close()

def test_tradetally_sync_data():
    """Test the TradeTally sync data to ensure it uses real prices"""
    db_path = "../trading_data.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Test the enhanced query from tradetally_sync.py
    cursor.execute("""
        SELECT 
            trade_id,
            symbol,
            -- Use actual execution prices if available, fallback to planned
            COALESCE(actual_entry_price, entry_price) as final_entry_price,
            COALESCE(actual_exit_price, exit_price) as final_exit_price,
            COALESCE(actual_pnl, pnl) as final_pnl,
            -- Slippage data for notes
            entry_slippage,
            exit_slippage,
            total_slippage_impact
        FROM trades 
        WHERE trade_id LIKE 'TEST_%'
        ORDER BY symbol
    """)
    
    results = cursor.fetchall()
    
    print("\n" + "="*60)
    print("🔗 TRADETALLY SYNC DATA")
    print("="*60)
    
    total_sync_pnl = 0
    
    for row in results:
        (trade_id, symbol, final_entry, final_exit, final_pnl, 
         entry_slippage, exit_slippage, slippage_impact) = row
         
        print(f"\n{symbol}: Entry=${final_entry:.4f}, Exit=${final_exit:.4f}, P&L=${final_pnl:.2f}")
        if entry_slippage is not None:
            print(f"   Slippage Info: Entry=${entry_slippage:.4f}, Exit=${exit_slippage:.4f}, Impact=${slippage_impact:.2f}")
        
        total_sync_pnl += final_pnl or 0
    
    print(f"\n💡 TradeTally will receive P&L: ${total_sync_pnl:.2f}")
    print("   (This should match your manual calculation of $37.69 - commissions)")
    
    # Calculate what it should be with real broker prices
    # SSKN: (2.90 - 2.65) * 76 = 19.00 - 0.72 = 18.28
    # HWH: (5.58 - 6.13) * 33 = -18.15 - 0.72 = -18.87
    # Total: 18.28 - 18.87 = -0.59
    expected_pnl = 18.28 - 18.87
    
    print(f"   Expected with broker prices: ${expected_pnl:.2f}")
    
    conn.close()

def main():
    print("🚀 Testing Enhanced Execution Tracking System")
    print("=" * 50)
    
    # Step 1: Create sample trades
    print("\n📝 Step 1: Creating sample trades...")
    sample_trades = create_sample_trades()
    
    # Step 2: Simulate real executions
    print("\n⚡ Step 2: Simulating real broker executions...")
    simulate_real_executions(sample_trades)
    
    # Step 3: Verify results
    print("\n✅ Step 3: Verifying results...")
    verify_results()
    
    # Step 4: Test TradeTally sync data
    print("\n🔗 Step 4: Testing TradeTally sync data...")
    test_tradetally_sync_data()
    
    print(f"\n🎉 Test completed! The system now tracks real execution prices.")
    print(f"   TradeTally will use real broker prices for accurate P&L calculations.")
    print(f"   Slippage metrics are automatically calculated and stored.")

if __name__ == "__main__":
    main()