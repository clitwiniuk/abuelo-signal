#!/usr/bin/env python3
"""
Generate Trade Replay Viewer
============================
Crea visualizaciones tipo "electroencefalograma" de trades grabados.
Muestra el precio moviéndose dentro de los límites del worker (SL/TP).

Uso:
    python generate_trade_replay.py <trade_id> [output.html]
    python generate_trade_replay.py 1000094
    python generate_trade_replay.py latest
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = Path(__file__).parent.parent / "trading_data.db"
TEMPLATE_PATH = Path(__file__).parent / "trade_replay_viewer.html"


def get_trade_data(trade_id: str) -> dict:
    """Extrae datos completos del trade desde la base de datos"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Si trade_id es "latest", obtener el último trade
    if trade_id.lower() == "latest":
        cursor.execute("""
            SELECT trade_id FROM trades
            WHERE exit_time IS NOT NULL
            ORDER BY entry_time DESC LIMIT 1
        """)
        result = cursor.fetchone()
        if not result:
            raise ValueError("No se encontraron trades cerrados")
        trade_id = result[0]
        print(f"📊 Usando el trade más reciente: {trade_id}")

    # Obtener datos del trade con OHLC
    cursor.execute("""
        SELECT
            t.trade_id, t.symbol, t.worker_name, t.entry_price, t.exit_price,
            t.stop_loss_pct, t.take_profit_pct, t.trailing_activation_pct, t.trailing_distance_pct,
            t.stop_loss_price, t.take_profit_price, t.entry_time, t.exit_time, t.exit_reason_detailed,
            o.intraday_bars, o.day_open, o.day_high, o.day_low, o.day_close
        FROM trades t
        JOIN trade_ohlc_snapshots o ON t.trade_id = o.trade_id
        WHERE t.trade_id = ?
    """, (trade_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Trade {trade_id} no encontrado o sin datos OHLC")

    # Parse intraday bars
    intraday_bars = json.loads(row[14]) if row[14] else []

    # Filtrar barras desde entry hasta exit
    # Las barras contienen TODO el día, necesitamos filtrar solo el rango del trade
    entry_time = datetime.fromisoformat(row[11].replace(' ', 'T'))
    exit_time = datetime.fromisoformat(row[12].replace(' ', 'T')) if row[12] else None

    filtered_bars = []
    for bar in intraday_bars:
        # Parse timestamp que puede venir en diferentes formatos
        timestamp_str = bar['timestamp']
        # Normalizar timezone
        timestamp_str = timestamp_str.replace('-05:00', '').replace('-04:00', '')
        if 'T' in timestamp_str:
            timestamp_str = timestamp_str.replace('T', ' ')

        try:
            bar_time = datetime.fromisoformat(timestamp_str)
        except ValueError:
            continue

        # Incluir barras desde entry hasta exit
        # Como las barras son del día completo, tomamos todas (para ver contexto)
        filtered_bars.append(bar)

    trade_data = {
        'trade_id': row[0],
        'symbol': row[1],
        'worker_name': row[2],
        'entry_price': row[3],
        'exit_price': row[4] if row[4] else row[3],  # Si no hay exit, usar entry
        'stop_loss_pct': row[5],
        'take_profit_pct': row[6],
        'trailing_activation_pct': row[7],
        'trailing_distance_pct': row[8],
        'stop_loss_price': row[9],
        'take_profit_price': row[10],
        'entry_time': row[11],
        'exit_time': row[12] if row[12] else row[11],
        'exit_reason': row[13] if row[13] else 'N/A',
        'day_open': row[15],
        'day_high': row[16],
        'day_low': row[17],
        'day_close': row[18],
        'bars': filtered_bars
    }

    conn.close()
    return trade_data


def generate_html(trade_data: dict, output_path: Path):
    """Genera el archivo HTML con los datos del trade"""

    # Leer template
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Convertir datos a JSON para JavaScript
    bars_json = json.dumps(trade_data['bars'])

    # Crear el objeto de datos completo
    trade_data_js = f"""
        const TRADE_DATA = {{
            trade_id: "{trade_data['trade_id']}",
            symbol: "{trade_data['symbol']}",
            worker_name: "{trade_data['worker_name']}",
            entry_price: {trade_data['entry_price']},
            exit_price: {trade_data['exit_price']},
            stop_loss_price: {trade_data['stop_loss_price']},
            take_profit_price: {trade_data['take_profit_price']},
            entry_time: "{trade_data['entry_time']}",
            exit_time: "{trade_data['exit_time']}",
            exit_reason: "{trade_data['exit_reason']}",
            bars: {bars_json}
        }};

        // Reemplazar el placeholder con datos reales
        Object.assign(TRADE_DATA_PLACEHOLDER, TRADE_DATA);
        allBars = TRADE_DATA.bars;

        console.log('✅ Datos del trade cargados:', TRADE_DATA.trade_id);
        console.log(`📊 ${{TRADE_DATA.symbol}} - ${{TRADE_DATA.bars.length}} barras`);
    """

    # Inyectar datos en el HTML (justo antes del cierre de </script>)
    html_content = html_content.replace(
        '// This will be replaced by actual data loading',
        trade_data_js
    )

    # Escribir archivo de salida
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Archivo generado: {output_path}")
    print(f"📊 Trade: {trade_data['trade_id']} - {trade_data['symbol']}")
    print(f"📈 Barras: {len(trade_data['bars'])}")
    print(f"💰 Entry: ${trade_data['entry_price']:.3f} → Exit: ${trade_data['exit_price']:.3f}")

    pnl = ((trade_data['exit_price'] / trade_data['entry_price'] - 1) * 100)
    pnl_str = f"+{pnl:.2f}%" if pnl >= 0 else f"{pnl:.2f}%"
    print(f"📊 P&L: {pnl_str}")


def main():
    if len(sys.argv) < 2:
        print("❌ Error: Falta el trade_id")
        print("\nUso:")
        print("  python generate_trade_replay.py <trade_id> [output.html]")
        print("  python generate_trade_replay.py 1000094")
        print("  python generate_trade_replay.py latest")
        sys.exit(1)

    trade_id = sys.argv[1]
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f"trade_replay_{trade_id}.html")

    try:
        print(f"🔍 Cargando trade {trade_id}...")
        trade_data = get_trade_data(trade_id)

        print(f"📝 Generando visualización...")
        generate_html(trade_data, output_path)

        print(f"\n🎯 Listo! Abre el archivo en tu navegador:")
        print(f"   file://{output_path.absolute()}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
