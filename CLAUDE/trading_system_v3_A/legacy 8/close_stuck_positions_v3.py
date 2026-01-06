#!/usr/bin/env python3
"""
Script para cerrar posiciones atrapadas en v3 (paper trading)
Cierra las posiciones que quedaron abiertas después del EOD
"""

import sqlite3
from datetime import datetime

def close_stuck_positions():
    """Cierra las posiciones OPEN de NUAI, SLS, ONDS del 31/12/2025"""

    db_path = "trading_data.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Obtener posiciones abiertas
    cursor.execute("""
        SELECT trade_id, symbol, entry_price, quantity, worker_name, entry_time
        FROM trades
        WHERE status = 'OPEN'
        AND symbol IN ('NUAI', 'SLS', 'ONDS')
        AND date(entry_time) = '2025-12-31'
        ORDER BY entry_time
    """)

    open_positions = cursor.fetchall()

    if not open_positions:
        print("✅ No hay posiciones abiertas de NUAI, SLS, ONDS del 31/12")
        conn.close()
        return

    print(f"📊 Encontradas {len(open_positions)} posiciones para cerrar:\n")

    for trade_id, symbol, entry_price, quantity, worker, entry_time in open_positions:
        print(f"  • {symbol}: Trade #{trade_id}, Entry: ${entry_price}, Qty: {quantity}, Worker: {worker}")

    print("\n🔄 Cerrando automáticamente...")

    # Precio de cierre para cada símbolo (aproximado del último precio del día)
    exit_prices = {
        'NUAI': 2.83,  # Aproximado
        'SLS': 3.81,   # Aproximado
        'ONDS': 9.78   # Aproximado
    }

    exit_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Cerrar cada posición
    for trade_id, symbol, entry_price, quantity, worker, entry_time in open_positions:
        exit_price = exit_prices.get(symbol, entry_price)  # Fallback a entry_price

        # Calcular PnL
        pnl = (exit_price - entry_price) * quantity
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100

        # Actualizar trade
        cursor.execute("""
            UPDATE trades
            SET status = 'CLOSED',
                exit_price = ?,
                exit_time = ?,
                pnl = ?,
                exit_reason_detailed = ?
            WHERE trade_id = ?
        """, (exit_price, exit_time, pnl, 'MANUAL_CLOSE_STUCK_EOD', trade_id))

        print(f"  ✅ {symbol} cerrado: Entry=${entry_price:.2f}, Exit=${exit_price:.2f}, PnL={pnl_pct:+.2f}% (${pnl:+.2f})")

    # Commit cambios
    conn.commit()
    conn.close()

    print(f"\n✅ {len(open_positions)} posiciones cerradas correctamente")
    print(f"⏰ Hora de cierre registrada: {exit_time}")

if __name__ == "__main__":
    print("=" * 60)
    print("CERRAR POSICIONES ATRAPADAS - v3 Paper Trading")
    print("=" * 60)
    print()

    close_stuck_positions()
