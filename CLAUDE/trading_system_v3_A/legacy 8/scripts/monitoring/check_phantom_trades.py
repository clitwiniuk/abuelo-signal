#!/usr/bin/env python3
"""
Phantom Trade Monitor
Detecta y reporta trades phantom que se crean incorrectamente durante afterhours
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PhantomTradeMonitor:
    """Monitor para detectar phantom trades"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def check_recent_phantom_trades(self, hours: int = 24):
        """Buscar phantom trades recientes"""

        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                trade_id,
                symbol,
                entry_time,
                exit_time,
                entry_price,
                exit_price,
                pnl,
                status,
                notes
            FROM trades
            WHERE (notes LIKE '%PHANTOM%' OR notes LIKE '%AUTO_CLOSED%')
            AND created_at > ?
            ORDER BY created_at DESC
        """, (cutoff_str,))

        phantom_trades = cursor.fetchall()

        if phantom_trades:
            logger.warning(f"🚨 FOUND {len(phantom_trades)} PHANTOM TRADES in last {hours} hours!")
            for trade in phantom_trades:
                logger.warning(
                    f"  - {trade['symbol']} ({trade['trade_id']}): "
                    f"Entry: {trade['entry_time']}, "
                    f"Exit: {trade['exit_time']}, "
                    f"PnL: ${trade['pnl']}, "
                    f"Notes: {trade['notes']}"
                )
            return list(phantom_trades)
        else:
            logger.info(f"✅ No phantom trades found in last {hours} hours")
            return []

    def check_afterhours_trades(self, hours: int = 24):
        """Buscar trades creados durante horario afterhours sospechoso"""

        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                trade_id,
                symbol,
                entry_time,
                entry_price,
                status,
                notes
            FROM trades
            WHERE created_at > ?
            AND strftime('%H', entry_time) BETWEEN '20' AND '23'
            AND status = 'OPEN'
            ORDER BY entry_time DESC
        """, (cutoff_str,))

        suspicious_trades = cursor.fetchall()

        if suspicious_trades:
            logger.warning(
                f"⚠️  FOUND {len(suspicious_trades)} trades opened during late hours (20:00-23:59):"
            )
            for trade in suspicious_trades:
                logger.warning(
                    f"  - {trade['symbol']} ({trade['trade_id']}): "
                    f"Entry: {trade['entry_time']}, "
                    f"Price: ${trade['entry_price']}, "
                    f"Status: {trade['status']}"
                )
            return list(suspicious_trades)
        else:
            logger.info("✅ No suspicious afterhours trades found")
            return []

    def get_statistics(self):
        """Obtener estadísticas generales"""

        cursor = self.conn.cursor()

        # Total trades
        cursor.execute("SELECT COUNT(*) FROM trades")
        total = cursor.fetchone()[0]

        # Phantom trades
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE notes LIKE '%PHANTOM%' OR notes LIKE '%AUTO_CLOSED%'
        """)
        phantom = cursor.fetchone()[0]

        # Open trades
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
        open_trades = cursor.fetchone()[0]

        # Closed trades
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'")
        closed_trades = cursor.fetchone()[0]

        logger.info("📊 Trade Statistics:")
        logger.info(f"  Total trades: {total}")
        logger.info(f"  Phantom trades: {phantom}")
        logger.info(f"  Open trades: {open_trades}")
        logger.info(f"  Closed trades: {closed_trades}")
        logger.info(f"  Valid trades: {closed_trades - phantom}")

        return {
            'total': total,
            'phantom': phantom,
            'open': open_trades,
            'closed': closed_trades,
            'valid': closed_trades - phantom
        }

    def close(self):
        """Cerrar conexión"""
        if self.conn:
            self.conn.close()

def main():
    """Función principal"""

    # Ruta a la base de datos
    db_path = Path(__file__).parent.parent.parent / "trading_data.db"

    if not db_path.exists():
        logger.error(f"❌ Database not found: {db_path}")
        return

    monitor = PhantomTradeMonitor(str(db_path))

    try:
        logger.info("🔍 Checking for phantom trades...")
        logger.info("=" * 60)

        # Estadísticas generales
        stats = monitor.get_statistics()
        logger.info("")

        # Buscar phantom trades recientes (últimas 24 horas)
        logger.info("🔍 Checking recent phantom trades (last 24h)...")
        phantom_trades = monitor.check_recent_phantom_trades(hours=24)
        logger.info("")

        # Buscar trades sospechosos en afterhours (últimas 24 horas)
        logger.info("🔍 Checking suspicious afterhours trades (last 24h)...")
        suspicious_trades = monitor.check_afterhours_trades(hours=24)
        logger.info("")

        logger.info("=" * 60)

        if phantom_trades or suspicious_trades:
            logger.warning("⚠️  ACTION REQUIRED: Review phantom/suspicious trades above")
            logger.warning("   Consider investigating your trade execution logic during afterhours")
        else:
            logger.info("✅ All clear! No phantom or suspicious trades detected")

    except Exception as e:
        logger.error(f"❌ Error during monitoring: {e}")
    finally:
        monitor.close()

if __name__ == "__main__":
    main()
