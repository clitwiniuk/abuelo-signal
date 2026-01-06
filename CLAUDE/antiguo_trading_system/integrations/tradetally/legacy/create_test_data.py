#!/usr/bin/env python3
"""
Generador de datos de prueba para TradeTally Integration
Crea trades de ejemplo en la base de datos local para testing
"""

import sqlite3
import random
from datetime import datetime, timedelta
import uuid
from pathlib import Path

def create_test_trades(db_path: str, num_trades: int = 10):
    """Crear trades de prueba en la base de datos"""
    
    # Símbolos de ejemplo
    symbols = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 
        'NVDA', 'META', 'NFLX', 'AMD', 'ROKU',
        'PLTR', 'NIO', 'COIN', 'GME', 'AMC'
    ]
    
    # Estrategias de ejemplo
    strategies = [
        'Gap Go Strategy',
        'Volume Explosion',
        'VWAP Reclaim',
        'Momentum Breakout',
        'Scalping',
        'Swing Trade',
        'News Play'
    ]
    
    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"📊 Creando {num_trades} trades de prueba...")
    
    trades_created = 0
    
    for i in range(num_trades):
        # Generar datos aleatorios pero realistas
        symbol = random.choice(symbols)
        strategy = random.choice(strategies)
        side = random.choice(['BUY', 'SELL'])
        
        # Precios realistas
        base_price = random.uniform(10, 500)
        entry_price = round(base_price, 2)
        
        # Simuler movimiento de precio (±5%)
        price_change_pct = random.uniform(-0.05, 0.05)
        exit_price = round(entry_price * (1 + price_change_pct), 2)
        
        # Cantidad
        quantity = random.choice([100, 200, 300, 500, 1000])
        
        # Tiempos
        days_ago = random.randint(1, 30)
        entry_time = datetime.now() - timedelta(days=days_ago, 
                                               hours=random.randint(9, 15),
                                               minutes=random.randint(0, 59))
        
        # Duración del trade (30 min a 6 horas)
        duration_minutes = random.randint(30, 360)
        exit_time = entry_time + timedelta(minutes=duration_minutes)
        
        # Calcular PnL
        if side == 'BUY':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        # Comisión realista
        commission = round(quantity * 0.001 + random.uniform(0.5, 2.0), 2)
        
        # PnL neto
        pnl_net = round(pnl - commission, 2)
        
        # ID único
        trade_id = f"TEST_{uuid.uuid4().hex[:8].upper()}"
        
        # Notas de ejemplo
        notes_options = [
            "Strong volume breakout",
            "News catalyst play",
            "Technical breakout above resistance", 
            "Gap fill trade",
            "Momentum follow-through",
            "Quick scalp on volume",
            "Trend continuation play"
        ]
        notes = random.choice(notes_options)
        
        # Insertar en la base de datos
        try:
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, strategy, side, quantity,
                    entry_price, exit_price, entry_time, exit_time,
                    duration_minutes, pnl, commission, status, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id, symbol, strategy, side, quantity,
                entry_price, exit_price, 
                entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                exit_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_minutes, pnl_net, commission, 'CLOSED', notes,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            trades_created += 1
            
            # Mostrar progreso
            profit_emoji = "📈" if pnl_net > 0 else "📉"
            print(f"  {i+1:2d}. {symbol:6s} {side:4s} {quantity:4d} @ ${entry_price:7.2f} → ${exit_price:7.2f} "
                  f"{profit_emoji} ${pnl_net:8.2f} ({strategy})")
            
        except sqlite3.IntegrityError as e:
            print(f"⚠️  Error insertando trade {trade_id}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ {trades_created} trades de prueba creados exitosamente!")
    return trades_created

def show_test_data_summary(db_path: str):
    """Mostrar resumen de los datos de prueba"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Estadísticas generales
    cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'")
    total_trades = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(pnl), AVG(pnl) FROM trades WHERE status = 'CLOSED'")
    total_pnl, avg_pnl = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND pnl > 0")
    winning_trades = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND pnl < 0")
    losing_trades = cursor.fetchone()[0]
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    print(f"""
📊 RESUMEN DE DATOS DE PRUEBA
{'='*50}
📈 Total Trades: {total_trades}
💰 PnL Total: ${total_pnl:.2f}
📊 PnL Promedio: ${avg_pnl:.2f}
✅ Trades Ganadores: {winning_trades}
❌ Trades Perdedores: {losing_trades}
🎯 Win Rate: {win_rate:.1f}%
""")
    
    # Top 5 trades por PnL
    print("🏆 TOP 5 MEJORES TRADES:")
    cursor.execute("""
        SELECT symbol, side, quantity, entry_price, exit_price, pnl, strategy
        FROM trades 
        WHERE status = 'CLOSED'
        ORDER BY pnl DESC 
        LIMIT 5
    """)
    
    for i, trade in enumerate(cursor.fetchall(), 1):
        symbol, side, qty, entry, exit, pnl, strategy = trade
        print(f"  {i}. {symbol} {side} {qty}@${entry:.2f}→${exit:.2f} = ${pnl:.2f} ({strategy})")
    
    # Símbolos más traded
    print("\n📊 SÍMBOLOS MÁS OPERADOS:")
    cursor.execute("""
        SELECT symbol, COUNT(*) as trades, SUM(pnl) as total_pnl
        FROM trades 
        WHERE status = 'CLOSED'
        GROUP BY symbol
        ORDER BY trades DESC
        LIMIT 5
    """)
    
    for symbol, count, pnl in cursor.fetchall():
        print(f"  • {symbol}: {count} trades, ${pnl:.2f} PnL")
    
    conn.close()

def clear_test_data(db_path: str):
    """Limpiar todos los datos de prueba"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Eliminar trades que empiecen con "TEST_"
    cursor.execute("DELETE FROM trades WHERE trade_id LIKE 'TEST_%'")
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"🗑️  {deleted} trades de prueba eliminados")
    return deleted

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generador de datos de prueba para TradeTally")
    parser.add_argument('--create', '-c', type=int, default=10, 
                       help='Crear N trades de prueba (default: 10)')
    parser.add_argument('--summary', '-s', action='store_true',
                       help='Mostrar resumen de datos actuales')
    parser.add_argument('--clear', action='store_true',
                       help='Limpiar todos los datos de prueba')
    parser.add_argument('--db-path', default='../trading_data.db',
                       help='Ruta a la base de datos')
    
    args = parser.parse_args()
    
    # Resolver ruta de la base de datos
    db_path = Path(__file__).parent.parent / "trading_data.db"
    if not db_path.exists():
        print(f"❌ Base de datos no encontrada: {db_path}")
        return
    
    print(f"🗄️  Usando base de datos: {db_path}")
    
    if args.clear:
        clear_test_data(str(db_path))
    elif args.summary:
        show_test_data_summary(str(db_path))
    else:
        create_test_trades(str(db_path), args.create)
        print()
        show_test_data_summary(str(db_path))

if __name__ == "__main__":
    main()