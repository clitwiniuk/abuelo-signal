"""
Trade Event Logger - Captura eventos de trading para análisis de TP/SL

Registra TODAS las señales generadas (entradas y rechazos) para:
- Event Study de TP/SL óptimo
- Análisis de forward returns
- Cálculo de percentiles por worker/confidence/ODS
- Optimización basada en datos reales

Author: Trading System
Date: 2025-11-09
"""

import sqlite3
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class TradeEventLogger:
    """
    Registra eventos de señales de trading para análisis posterior

    Captura:
    - Todas las señales generadas (entradas + rechazos)
    - Contexto ODS/Structure en momento de señal
    - Forward returns (rellenados por proceso separado)
    - MFE/MAE para trades ejecutados
    """

    def __init__(self, db_path: str = "trading_data.db"):
        """
        Inicializa logger

        Args:
            db_path: Ruta a base de datos SQLite
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)

        # Verificar que DB existe
        if not Path(db_path).exists():
            self.logger.warning(f"Database {db_path} not found - will be created on first log")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def log_signal_event(
        self,
        worker_name: str,
        symbol: str,
        entry_price: float,
        opportunity: Dict[str, Any],
        entered: bool,
        rejection_reason: Optional[str] = None,
        trade_id: Optional[str] = None
    ) -> str:
        """
        Registra evento de señal (entrada o rechazo)

        Args:
            worker_name: Nombre del worker que generó señal
            symbol: Símbolo
            entry_price: Precio de entrada propuesto
            opportunity: Dict completo con todos los datos
            entered: True si se ejecutó la entrada
            rejection_reason: Razón de rechazo si no entró
            trade_id: ID del trade si se ejecutó

        Returns:
            signal_id: UUID del evento registrado
        """
        signal_id = str(uuid.uuid4())

        try:
            # Extraer datos del opportunity
            ods_data = opportunity.get('ods_data', {})
            structure_data = opportunity.get('intraday_structure', {})

            # Helper function to safely get values from dict or object
            def safe_get(obj, attr, default=None):
                """
                Get attribute from dict or object, converting Enums to strings for SQL compatibility
                """
                if obj is None:
                    return default

                # Get value from dict or object
                if isinstance(obj, dict):
                    value = obj.get(attr, default)
                else:
                    value = getattr(obj, attr, default)

                # Convert Enum to string (for SQL binding compatibility)
                if value is not None and hasattr(value, 'value'):
                    # It's an Enum - return its value as string
                    return str(value.value) if not isinstance(value.value, str) else value.value

                return value

            # Preparar datos
            data = {
                'signal_id': signal_id,
                'symbol': symbol,
                'worker_name': worker_name,
                'timestamp': datetime.now(),
                'entered': entered,
                'rejection_reason': rejection_reason,
                'trade_id': trade_id,

                # Precios
                'entry_price': entry_price,
                'invalid_price': opportunity.get('invalid_price'),  # Si worker lo calculó
                'suggested_sl': opportunity.get('suggested_stop_loss'),
                'suggested_tp': opportunity.get('suggested_take_profit'),

                # Contexto ODS
                'ods_classification': safe_get(ods_data, 'classification'),
                'ods_strength': safe_get(ods_data, 'strength'),
                'ods_direction': safe_get(ods_data, 'direction'),

                # Contexto Structure
                'intraday_phase': safe_get(structure_data, 'current_phase'),
                'continuation_type': safe_get(structure_data, 'continuation_type'),
                'liquidity_sweep_detected': safe_get(structure_data, 'liquidity_sweep_detected', False),
                'sweep_direction': safe_get(structure_data, 'sweep_direction'),

                # Métricas
                'confidence': opportunity.get('confidence'),
                'quality_score': opportunity.get('quality_score'),
                'atr_percent': opportunity.get('atr_percent'),
                'volume_ratio': opportunity.get('volume_ratio'),
                'gap_percentage': opportunity.get('gap_percentage'),
                'catalyst_type': opportunity.get('catalyst_type'),
                'catalyst_strength': opportunity.get('catalyst_strength'),
            }

            # Insertar en DB
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO signal_events (
                    signal_id, symbol, worker_name, timestamp,
                    entered, rejection_reason, trade_id,
                    entry_price, invalid_price, suggested_sl, suggested_tp,
                    ods_classification, ods_strength, ods_direction,
                    intraday_phase, continuation_type,
                    liquidity_sweep_detected, sweep_direction,
                    confidence, quality_score, atr_percent,
                    volume_ratio, gap_percentage,
                    catalyst_type, catalyst_strength
                ) VALUES (
                    :signal_id, :symbol, :worker_name, :timestamp,
                    :entered, :rejection_reason, :trade_id,
                    :entry_price, :invalid_price, :suggested_sl, :suggested_tp,
                    :ods_classification, :ods_strength, :ods_direction,
                    :intraday_phase, :continuation_type,
                    :liquidity_sweep_detected, :sweep_direction,
                    :confidence, :quality_score, :atr_percent,
                    :volume_ratio, :gap_percentage,
                    :catalyst_type, :catalyst_strength
                )
            ''', data)

            conn.commit()
            conn.close()

            self.logger.info(
                f"📝 Signal event logged: {worker_name} - {symbol} @ ${entry_price:.2f} "
                f"({'ENTERED' if entered else 'REJECTED'})"
            )

            return signal_id

        except Exception as e:
            self.logger.error(f"Failed to log signal event: {e}")
            raise

    def update_trade_context(
        self,
        trade_id: str,
        worker_name: str,
        opportunity: Dict[str, Any]
    ):
        """
        Actualiza tabla 'trades' con contexto ODS/Structure

        Args:
            trade_id: ID del trade en tabla trades
            worker_name: Worker que generó la entrada
            opportunity: Opportunity dict con contexto
        """
        try:
            ods_data = opportunity.get('ods_data', {})
            structure_data = opportunity.get('intraday_structure', {})

            # Helper function to safely get values from dict or object
            def safe_get(obj, attr, default=None):
                """
                Get attribute from dict or object, converting Enums to strings for SQL compatibility
                """
                if obj is None:
                    return default

                # Get value from dict or object
                if isinstance(obj, dict):
                    value = obj.get(attr, default)
                else:
                    value = getattr(obj, attr, default)

                # Convert Enum to string (for SQL binding compatibility)
                if value is not None and hasattr(value, 'value'):
                    # It's an Enum - return its value as string
                    return str(value.value) if not isinstance(value.value, str) else value.value

                return value

            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE trades SET
                    worker_name = ?,
                    ods_classification = ?,
                    ods_strength = ?,
                    intraday_phase = ?,
                    continuation_type = ?,
                    liquidity_sweep_detected = ?,
                    atr_percent_at_entry = ?,
                    invalid_price = ?,
                    suggested_sl_price = ?,
                    suggested_tp_price = ?
                WHERE trade_id = ?
            ''', (
                worker_name,
                safe_get(ods_data, 'classification'),
                safe_get(ods_data, 'strength'),
                safe_get(structure_data, 'current_phase'),
                safe_get(structure_data, 'continuation_type'),
                safe_get(structure_data, 'liquidity_sweep_detected', False),
                opportunity.get('atr_percent'),
                opportunity.get('invalid_price'),
                opportunity.get('suggested_stop_loss'),
                opportunity.get('suggested_take_profit'),
                trade_id
            ))

            conn.commit()
            conn.close()

            self.logger.debug(f"Trade context updated for {trade_id}")

        except Exception as e:
            self.logger.error(f"Failed to update trade context: {e}")

    def get_pending_forward_tracking(self, hours_back: int = 24) -> list:
        """
        Obtiene señales que necesitan forward tracking

        Args:
            hours_back: Cuántas horas atrás buscar

        Returns:
            Lista de signal_events que necesitan tracking
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT *
                FROM signal_events
                WHERE forward_tracked_at IS NULL
                  AND timestamp >= datetime('now', '-' || ? || ' hours')
                  AND timestamp <= datetime('now', '-5 minutes')  -- Al menos 5min de edad
                ORDER BY timestamp
            ''', (hours_back,))

            results = cursor.fetchall()
            conn.close()

            return [dict(row) for row in results]

        except Exception as e:
            self.logger.error(f"Failed to get pending tracking: {e}")
            return []

    def update_forward_returns(
        self,
        signal_id: str,
        forward_5m: Optional[float] = None,
        forward_15m: Optional[float] = None,
        forward_60m: Optional[float] = None,
        forward_240m: Optional[float] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None
    ):
        """
        Actualiza forward returns para una señal

        Args:
            signal_id: ID de la señal
            forward_5m: Return a 5 minutos (decimal, e.g., 0.02 = 2%)
            forward_15m: Return a 15 minutos
            forward_60m: Return a 60 minutos
            forward_240m: Return a 240 minutos
            max_price: Precio máximo alcanzado
            min_price: Precio mínimo alcanzado
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get entry price to calculate MFE/MAE
            cursor.execute('SELECT entry_price FROM signal_events WHERE signal_id = ?', (signal_id,))
            row = cursor.fetchone()

            if not row:
                self.logger.error(f"Signal {signal_id} not found")
                return

            entry_price = row['entry_price']

            # Calculate MFE/MAE if we have max/min prices
            mfe_percent = None
            mae_percent = None

            if max_price:
                mfe_percent = ((max_price - entry_price) / entry_price) * 100

            if min_price:
                mae_percent = ((min_price - entry_price) / entry_price) * 100

            # Update
            cursor.execute('''
                UPDATE signal_events SET
                    forward_return_5m = ?,
                    forward_return_15m = ?,
                    forward_return_60m = ?,
                    forward_return_240m = ?,
                    max_price_reached = ?,
                    min_price_reached = ?,
                    mfe_percent = ?,
                    mae_percent = ?,
                    forward_tracked_at = datetime('now')
                WHERE signal_id = ?
            ''', (
                forward_5m,
                forward_15m,
                forward_60m,
                forward_240m,
                max_price,
                min_price,
                mfe_percent,
                mae_percent,
                signal_id
            ))

            conn.commit()
            conn.close()

            self.logger.debug(f"Forward returns updated for signal {signal_id}")

        except Exception as e:
            self.logger.error(f"Failed to update forward returns: {e}")
