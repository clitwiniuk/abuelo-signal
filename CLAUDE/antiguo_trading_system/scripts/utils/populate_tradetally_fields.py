#!/usr/bin/env python3
"""
Script para poblar campos vacíos en TradeTally sync
Ejecutar después de actualizar tradetally_sync.py
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradeTallyFieldPopulator:
    """Clase para poblar campos faltantes en trades"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connect_db()

    def connect_db(self):
        """Conectar a la base de datos"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def calculate_confidence(self, strategy: str, pnl: float = None, duration: int = None) -> float:
        """Calcular confidence basado en estrategia y resultado"""
        base_confidence = 50.0  # Base neutral

        # Ajustes por estrategia
        strategy_multipliers = {
            'VWAPReclaimStrategy': 1.2,
            'GapGoStrategy': 1.1,
            'VolumeBreakoutStrategy': 1.15,
            'ExplosiveVolumeStrategy': 0.9,
            'RSI_Divergence': 1.05,
            'swing_consolidation': 0.95,
            'swing_ascending_triangle': 1.1,
            'swing_descending_triangle': 1.05
        }

        if strategy in strategy_multipliers:
            base_confidence *= strategy_multipliers[strategy]

        # Ajuste por PnL si existe
        if pnl is not None:
            if pnl > 0:
                base_confidence += 15
            elif pnl < 0:
                base_confidence -= 10

        # Ajuste por duración (trades más largos pueden indicar mejor timing)
        if duration and duration > 30:
            base_confidence += 5
        elif duration and duration < 5:
            base_confidence -= 5

        return max(0, min(100, base_confidence))

    def determine_trade_session(self, entry_time: str) -> str:
        """Determinar sesión de trading basada en hora de entrada"""
        try:
            # Parsear timestamp (asumiendo formato YYYY-MM-DD HH:MM:SS)
            dt = datetime.fromisoformat(entry_time.replace('Z', ''))

            # Convertir a hora del este de US (donde operan los mercados)
            # Para simplificar, usaremos hora española + 6 horas para aproximar EST
            # España es CET/CEST (UTC+1/+2), EST es UTC-5/-4
            # Diferencia aproximada: España - EST = 6-7 horas

            hour = dt.hour

            # Ajustar por zona horaria (aproximado)
            est_hour = (hour - 6) % 24  # Aproximación simple

            if 9.5 <= est_hour < 10.5:
                return 'first_hour'
            elif 10.5 <= est_hour < 15.0:
                return 'midday'
            elif 15.0 <= est_hour < 16.0:
                return 'power_hour'
            elif est_hour < 9.5:
                return 'premarket'
            else:
                return 'afterhours'

        except Exception as e:
            logger.warning(f"Error determining session for {entry_time}: {e}")
            return 'unknown'

    def calculate_market_context_score(self, symbol: str, strategy: str) -> float:
        """Calcular score de contexto de mercado"""
        base_score = 60.0

        # Ajustes por tipo de estrategia
        if 'Gap' in strategy or 'Breakout' in strategy:
            base_score += 15  # Estas estrategias funcionan mejor en mercados trending
        elif 'VWAP' in strategy:
            base_score += 5   # VWAP funciona en mercados range/trending
        elif 'swing' in strategy.lower():
            base_score += 10  # Swing trading funciona en mercados con momentum

        # Podrías agregar lógica adicional basada en volatilidad del símbolo
        # Por ahora, devolver score base
        return max(0, min(100, base_score))

    def calculate_signal_strength(self, strategy: str, symbol: str, volume_ratio: float = None,
                                price_momentum: float = None, symbol_strength: float = None) -> float:
        """Calcular la fortaleza de la señal de entrada"""
        base_strength = 50.0  # Base neutral

        # Ajustes por estrategia (cada estrategia tiene diferente fortaleza base)
        strategy_strength = {
            'vwap_breakout': 75,      # VWAP breakouts son fuertes
            'VWAPReclaimStrategy': 70,
            'VolumeBreakoutStrategy': 80,  # Volume breakouts muy fuertes
            'GapGoStrategy': 85,      # Gaps son señales muy fuertes
            'ExplosiveVolumeStrategy': 65,  # Más ruido que señal
            'macdv': 60,              # MACD decente pero no excepcional
            'rsi_divergence': 70,     # RSI divergences son buenas señales
            'swing_consolidation': 55,
            'swing_ascending_triangle': 65,
            'swing_descending_triangle': 60
        }

        if strategy in strategy_strength:
            base_strength = strategy_strength[strategy]

        # Bonus por volume ratio (volumen alto = señal más fuerte)
        if volume_ratio and volume_ratio > 1.5:
            base_strength += 10
        elif volume_ratio and volume_ratio < 0.8:
            base_strength -= 10

        # Bonus por momentum (momentum fuerte = señal más fuerte)
        if price_momentum and abs(price_momentum) > 0.02:
            base_strength += 8
        elif price_momentum and abs(price_momentum) < 0.005:
            base_strength -= 5

        # Bonus por symbol strength (símbolos fuertes = mejores señales)
        if symbol_strength and symbol_strength > 0.1:
            base_strength += 5
        elif symbol_strength and symbol_strength < -0.1:
            base_strength -= 8

        return max(0, min(100, base_strength))

    def populate_fields(self):
        """Poblar campos faltantes en la base de datos"""
        logger.info("🔄 Iniciando población de campos TradeTally...")

        # Obtener todos los trades cerrados con campos adicionales
        self.cursor.execute("""
            SELECT id, trade_id, strategy, pnl, duration_minutes, entry_time,
                   confidence, trade_session, market_context_score, symbol,
                   volume_ratio, price_momentum, symbol_strength, signal_strength
            FROM trades
            WHERE status = 'CLOSED'
        """)

        trades = self.cursor.fetchall()
        logger.info(f"📊 Encontrados {len(trades)} trades para procesar")

        updated_count = 0

        for trade in trades:
            updates = {}

            # Calcular confidence si está vacío
            if trade['confidence'] is None:
                confidence = self.calculate_confidence(
                    trade['strategy'],
                    trade['pnl'],
                    trade['duration_minutes']
                )
                updates['confidence'] = confidence

            # Determinar sesión si está vacía
            if not trade['trade_session']:
                session = self.determine_trade_session(trade['entry_time'])
                updates['trade_session'] = session

            # Calcular market context score si está vacío
            if trade['market_context_score'] is None:
                context_score = self.calculate_market_context_score(
                    trade['symbol'],
                    trade['strategy']
                )
                updates['market_context_score'] = context_score

            # Calcular signal strength si está vacío
            if trade['signal_strength'] is None:
                signal_strength = self.calculate_signal_strength(
                    trade['strategy'],
                    trade['symbol'],
                    trade['volume_ratio'],
                    trade['price_momentum'],
                    trade['symbol_strength']
                )
                updates['signal_strength'] = signal_strength

            # Actualizar si hay cambios
            if updates:
                set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
                values = list(updates.values()) + [trade['id']]

                self.cursor.execute(f"""
                    UPDATE trades
                    SET {set_clause}
                    WHERE id = ?
                """, values)

                updated_count += 1
                logger.debug(f"✅ Actualizado trade {trade['trade_id']}: {updates}")

        self.conn.commit()
        logger.info(f"🏁 Proceso completado. {updated_count} trades actualizados")

    def show_sample_data(self):
        """Mostrar muestra de datos después de la actualización"""
        logger.info("📊 Muestra de datos actualizados:")

        self.cursor.execute("""
            SELECT trade_id, strategy, confidence, trade_session,
                   market_context_score, pnl, duration_minutes
            FROM trades
            WHERE status = 'CLOSED'
            ORDER BY created_at DESC
            LIMIT 5
        """)

        rows = self.cursor.fetchall()
        for row in rows:
            logger.info(f"  {dict(row)}")

    def close(self):
        """Cerrar conexión a BD"""
        if self.conn:
            self.conn.close()

def main():
    """Función principal"""
    # Get project root (2 levels up from scripts/utils/)
    db_path = Path(__file__).parent.parent.parent / "trading_data.db"

    if not db_path.exists():
        logger.error(f"❌ Base de datos no encontrada: {db_path}")
        logger.info(f"Buscando en: {db_path.absolute()}")
        return

    populator = TradeTallyFieldPopulator(str(db_path))

    try:
        logger.info("🔍 Mostrando datos antes de la actualización...")
        populator.show_sample_data()

        logger.info("\n🔄 Poblando campos...")
        populator.populate_fields()

        logger.info("\n📊 Mostrando datos después de la actualización...")
        populator.show_sample_data()

        logger.info("\n✅ Proceso completado exitosamente!")

    except Exception as e:
        logger.error(f"❌ Error durante el proceso: {e}")
    finally:
        populator.close()

if __name__ == "__main__":
    main()