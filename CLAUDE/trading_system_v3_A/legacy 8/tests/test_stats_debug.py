#!/usr/bin/env python3
"""
Test para diagnosticar diferencias entre /stats y datos del broker
"""

import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_stats_data_sources():
    """Test all data sources that /stats uses"""
    
    print("🔍 DIAGNÓSTICO DEL COMANDO /stats")
    print("=" * 60)
    
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 Fecha: {today}")
    
    # 1. Test Database Trades
    print("\n📊 1. DATOS DE BASE DE DATOS (trading_data.db)")
    print("-" * 40)
    
    db_path = project_root / "trading_data.db"
    if db_path.exists():
        try:
            with sqlite3.connect(db_path) as conn:
                # Count today's trades
                result = conn.execute(
                    "SELECT COUNT(*) FROM trades WHERE DATE(entry_time) = ?", 
                    (today,)
                ).fetchone()
                today_trades_db = result[0] if result else 0
                
                # Get recent trades details
                trades = conn.execute("""
                    SELECT symbol, entry_time, entry_price, quantity, status, pnl
                    FROM trades 
                    WHERE DATE(entry_time) = ?
                    ORDER BY entry_time DESC
                    LIMIT 10
                """, (today,)).fetchall()
                
                print(f"   Trades hoy (DB): {today_trades_db}")
                print(f"   Últimos trades:")
                for trade in trades:
                    symbol, entry_time, entry_price, qty, status, pnl = trade
                    pnl_str = f"${pnl:.2f}" if pnl else "N/A"
                    print(f"     • {symbol}: {entry_price} x{qty} - {status} - PnL: {pnl_str}")
                    
        except Exception as e:
            print(f"   ❌ Error leyendo DB: {e}")
            today_trades_db = 0
    else:
        print("   ❌ trading_data.db no existe")
        today_trades_db = 0
    
    # 2. Test Service Locator / Risk Manager
    print("\n🎯 2. DATOS DEL RISK MANAGER")
    print("-" * 40)
    
    try:
        from core.service_locator import get_service_locator
        service_locator = get_service_locator()
        
        # Get risk manager
        risk_manager = None
        if hasattr(service_locator, '_instances') and 'risk_manager' in service_locator._instances:
            risk_manager = service_locator._instances['risk_manager']
        
        if risk_manager:
            positions = getattr(risk_manager, 'broker_positions', {})
            current_positions = len(positions)
            
            print(f"   Posiciones actuales: {current_positions}")
            print(f"   Símbolos en broker_positions:")
            
            total_equity = 0
            for symbol, pos_data in positions.items():
                if isinstance(pos_data, dict):
                    market_value = pos_data.get('market_value', 0)
                    quantity = pos_data.get('quantity', 0)
                    avg_cost = pos_data.get('avg_cost', 0)
                    total_equity += abs(float(market_value)) if market_value else 0
                    
                    print(f"     • {symbol}: {quantity} shares @ ${avg_cost:.2f} = ${market_value:.2f}")
                else:
                    print(f"     • {symbol}: {type(pos_data)} (formato inesperado)")
            
            print(f"   Total equity calculado: ${total_equity:,.2f}")
            
        else:
            print("   ❌ Risk manager no disponible")
            current_positions = 0
            total_equity = 0
            
    except Exception as e:
        print(f"   ❌ Error accediendo service locator: {e}")
        current_positions = 0
        total_equity = 0
    
    # 3. Test Log Files
    print("\n📝 3. DATOS DE LOGS (trader.log)")
    print("-" * 40)
    
    trader_log_path = project_root / "logs" / "trader.log"
    today_signals = 0
    
    if trader_log_path.exists():
        try:
            with open(trader_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            signal_lines = []
            for line in lines:
                if line.startswith(today):
                    if any(keyword in line for keyword in ['Signal generated', 'ML Selected:', 'LONG SIGNAL', 'EXIT_LONG']):
                        today_signals += 1
                        signal_lines.append(line.strip())
            
            print(f"   Señales hoy (logs): {today_signals}")
            print(f"   Últimas señales:")
            for line in signal_lines[-5:]:  # Show last 5
                print(f"     • {line}")
                
        except Exception as e:
            print(f"   ❌ Error leyendo logs: {e}")
    else:
        print("   ❌ trader.log no existe")
    
    # 4. Test Broker Data Comparison
    print("\n💼 4. COMPARACIÓN CON BROKER")
    print("-" * 40)
    
    # Check if we can access broker data
    try:
        # Try to get broker adapter
        broker = None
        if 'service_locator' in locals() and hasattr(service_locator, '_instances'):
            if 'broker' in service_locator._instances:
                broker = service_locator._instances['broker']
        
        if broker and hasattr(broker, 'get_positions'):
            print("   🔍 Obteniendo posiciones del broker...")
            broker_positions = broker.get_positions()
            
            if isinstance(broker_positions, dict):
                print(f"   Posiciones del broker: {len(broker_positions)}")
                broker_equity = 0
                
                for symbol, pos in broker_positions.items():
                    market_val = getattr(pos, 'market_value', 0) if hasattr(pos, 'market_value') else 0
                    broker_equity += abs(float(market_val)) if market_val else 0
                    print(f"     • {symbol}: ${market_val:.2f}")
                
                print(f"   Total equity broker: ${broker_equity:,.2f}")
                
                # Compare
                print(f"\n   📊 COMPARACIÓN:")
                print(f"     Risk Manager equity: ${total_equity:,.2f}")
                print(f"     Broker equity:       ${broker_equity:,.2f}")
                print(f"     Diferencia:          ${abs(total_equity - broker_equity):,.2f}")
                
            else:
                print(f"   ❌ Formato de posiciones inesperado: {type(broker_positions)}")
        else:
            print("   ❌ Broker no disponible o no tiene método get_positions")
            
    except Exception as e:
        print(f"   ❌ Error accediendo broker: {e}")
    
    # 5. Summary
    print("\n" + "=" * 60)
    print("📋 RESUMEN DEL DIAGNÓSTICO")
    print("=" * 60)
    print(f"📊 Trades DB:           {today_trades_db}")
    print(f"📈 Señales logs:        {today_signals}")
    print(f"🎯 Posiciones sistema:  {current_positions}")
    print(f"💰 Equity sistema:      ${total_equity:,.2f}")
    print(f"📅 Fecha analizada:     {today}")
    
    return {
        'trades_db': today_trades_db,
        'signals_logs': today_signals,
        'positions_system': current_positions,
        'equity_system': total_equity,
        'date': today
    }

if __name__ == "__main__":
    results = test_stats_data_sources()