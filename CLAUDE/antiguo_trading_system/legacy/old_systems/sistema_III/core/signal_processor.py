#!/usr/bin/env python3
"""
Signal Processor with OHLC Integration
======================================

Procesador de señales que integra automáticamente la grabación OHLC
para forward testing y análisis de trades.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from core.interfaces import Signal, SignalType
from core.trade_ohlc_recorder import get_trade_ohlc_recorder


class SignalProcessor:
    """
    Procesador de señales con integración OHLC automática
    """

    def __init__(self, db_path: str = "trading_data.db"):
        self.logger = logging.getLogger("SignalProcessor")
        self.ohlc_recorder = get_trade_ohlc_recorder(db_path)

    def process_entry_signal(self, signal: Signal) -> bool:
        """
        Procesar señal de entrada y iniciar grabación OHLC

        Args:
            signal: Señal de entrada (LONG/SHORT)

        Returns:
            bool: True si se procesó correctamente
        """
        try:
            # Verificar que es señal de entrada
            if signal.signal_type not in [SignalType.LONG, SignalType.SHORT]:
                return False

            # Iniciar grabación OHLC para el trade
            success = self.ohlc_recorder.start_trade_recording(signal)

            if success:
                self.logger.info(f"📊 Started OHLC recording for {signal.symbol} trade {signal.signal_id[:8]}...")
            else:
                self.logger.warning(f"⚠️ Failed to start OHLC recording for {signal.symbol}")

            return success

        except Exception as e:
            self.logger.error(f"❌ Error processing entry signal: {e}")
            return False

    def process_exit_signal(self, signal: Signal, original_trade_id: str) -> bool:
        """
        Procesar señal de salida y completar grabación OHLC

        Args:
            signal: Señal de salida (EXIT_LONG/EXIT_SHORT)
            original_trade_id: ID del trade original que se está cerrando

        Returns:
            bool: True si se procesó correctamente
        """
        try:
            # Verificar que es señal de salida
            if signal.signal_type not in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                return False

            # Completar grabación OHLC
            success = self.ohlc_recorder.complete_trade_recording(original_trade_id, signal)

            if success:
                self.logger.info(f"✅ Completed OHLC recording for {signal.symbol} trade {original_trade_id[:8]}...")
            else:
                self.logger.warning(f"⚠️ Failed to complete OHLC recording for trade {original_trade_id}")

            return success

        except Exception as e:
            self.logger.error(f"❌ Error processing exit signal: {e}")
            return False

    def get_trade_analysis(self, trade_id: str) -> Optional[Dict]:
        """
        Obtener análisis completo de un trade

        Args:
            trade_id: ID del trade

        Returns:
            Dict con análisis completo o None si no existe
        """
        return self.ohlc_recorder.get_trade_ohlc_data(trade_id)


# Singleton global
_signal_processor = None

def get_signal_processor(db_path: str = "trading_data.db") -> SignalProcessor:
    """Obtener instancia singleton del procesador de señales"""
    global _signal_processor
    if _signal_processor is None:
        _signal_processor = SignalProcessor(db_path)
    return _signal_processor


# Funciones de utilidad para fácil integración
def record_entry_signal(signal: Signal) -> bool:
    """Función de utilidad para registrar señal de entrada"""
    processor = get_signal_processor()
    return processor.process_entry_signal(signal)


def record_exit_signal(signal: Signal, trade_id: str) -> bool:
    """Función de utilidad para registrar señal de salida"""
    processor = get_signal_processor()
    return processor.process_exit_signal(signal, trade_id)