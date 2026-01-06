#!/usr/bin/env python3
"""
Script para calcular automáticamente el confidence de trades existentes
usando la misma lógica de trading_execution_stage.py
"""

import sqlite3
import logging
from typing import Dict, List, Optional
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockSignalType(Enum):
    """Mock signal type para cálculo de confidence"""
    ENTRY_LONG = "ENTRY_LONG"
    ENTRY_SHORT = "ENTRY_SHORT"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"

class MockSignal:
    """Mock signal para cálculo de confidence"""
    def __init__(self, signal_type: str, strength: Optional[float] = None):
        # Convertir string a enum
        type_mapping = {
            'BUY': MockSignalType.ENTRY_LONG,
            'SELL': MockSignalType.ENTRY_SHORT,
            'long': MockSignalType.ENTRY_LONG,
            'short': MockSignalType.ENTRY_SHORT
        }
        
        self.signal_type = type_mapping.get(signal_type, MockSignalType.ENTRY_LONG)
        self.strength = strength
        self.confidence = None

def calculate_trade_confidence(signal: MockSignal, strategy_name: str) -> float:
    """
    Calcular confidence del trade basado en la señal y estrategia
    (Copiado directamente de trading_execution_stage.py)
    
    Args:
        signal: Señal de trading
        strategy_name: Nombre de la estrategia
        
    Returns:
        float: Confidence entre 0-100
    """
    try:
        base_confidence = 70.0  # Base confidence
        
        # 1. Usar signal strength si existe
        if hasattr(signal, 'strength') and signal.strength is not None:
            # Convertir strength (0-1) a confidence (0-100)
            signal_confidence = signal.strength * 100
            base_confidence = signal_confidence
        
        # 2. Usar confidence si existe (algunas estrategias lo incluyen)
        if hasattr(signal, 'confidence') and signal.confidence is not None:
            base_confidence = signal.confidence
        
        # 3. Ajustes por estrategia
        strategy_multipliers = {
            'GapGoStrategy': 1.1,      # Estrategia confiable
            'VolumeBreakoutStrategy': 1.05,
            'VWAPReclaimStrategy': 1.0,
            'ExplosiveVolumeStrategy': 0.95,
            'ImprovedSimpleExplosionStrategy': 0.9
        }
        
        multiplier = strategy_multipliers.get(strategy_name, 1.0)
        adjusted_confidence = base_confidence * multiplier
        
        # 4. Ajustes por tipo de señal
        signal_type_adjustments = {
            'ENTRY_LONG': 0,
            'ENTRY_SHORT': -5,  # Shorts generalmente más riesgosos
            'EXIT_LONG': 0,
            'EXIT_SHORT': 0
        }
        
        signal_adjustment = signal_type_adjustments.get(signal.signal_type.value, 0)
        final_confidence = adjusted_confidence + signal_adjustment
        
        # 5. Limitar entre 0-100
        final_confidence = max(0.0, min(100.0, final_confidence))
        
        logger.debug(f"Confidence calculated: {final_confidence:.1f}% "
                    f"(base: {base_confidence:.1f}, strategy: {strategy_name}, "
                    f"signal_type: {signal.signal_type.value})")
        
        return round(final_confidence, 1)
        
    except Exception as e:
        logger.error(f"Error calculating confidence: {e}")
        return 70.0  # Default confidence

def calculate_enhanced_confidence(trade_data: Dict) -> float:
    """
    Calcular confidence mejorado basado en datos del trade y métricas de performance
    
    Args:
        trade_data: Datos del trade de la base de datos
        
    Returns:
        float: Confidence calculado
    """
    try:
        # Crear mock signal
        signal = MockSignal(trade_data['side'])
        
        # Calcular confidence base usando la lógica de trading_execution_stage
        base_confidence = calculate_trade_confidence(signal, trade_data['strategy'] or 'Unknown')
        
        # Ajustes adicionales basados en resultados del trade
        performance_adjustments = 0
        
        # 1. Ajuste por PnL (si el trade fue exitoso, aumentar confidence retroactivamente)
        if trade_data['pnl'] is not None:
            pnl = float(trade_data['pnl'])
            if pnl > 0:
                # Trade exitoso: +5 points
                performance_adjustments += 5
            elif pnl < 0:
                # Trade perdedor: -3 points
                performance_adjustments -= 3
        
        # 2. Ajuste por duración del trade
        if trade_data['duration_minutes'] is not None:
            duration = int(trade_data['duration_minutes'])
            if duration < 5:  # Scalp muy rápido
                performance_adjustments -= 2
            elif 5 <= duration <= 60:  # Buena duración
                performance_adjustments += 2
            elif duration > 1440:  # Más de 1 día
                performance_adjustments -= 1
        
        # 3. Ajuste por symbol (algunos símbolos son más predecibles)
        symbol = trade_data['symbol']
        if symbol in ['SPY', 'QQQ', 'IWM']:  # ETFs principales
            performance_adjustments += 2
        elif symbol in ['TSLA', 'NVDA', 'AAPL', 'MSFT']:  # Blue chips volátiles
            performance_adjustments += 1
        
        # 4. Ajuste por hora de entrada (si disponible en entry_time)
        # Las 9:30-10:30 AM y 3:00-4:00 PM suelen ser mejores
        
        final_confidence = base_confidence + performance_adjustments
        final_confidence = max(0.0, min(100.0, final_confidence))
        
        return round(final_confidence, 1)
        
    except Exception as e:
        logger.error(f"Error in enhanced confidence calculation: {e}")
        return 70.0

def get_trades_without_confidence(db_path: str) -> List[Dict]:
    """Obtener trades que no tienen confidence"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trades 
            WHERE confidence IS NULL 
            AND status = 'CLOSED'
            ORDER BY entry_time DESC
        """)
        
        rows = cursor.fetchall()
        trades = [dict(row) for row in rows]
        conn.close()
        
        logger.info(f"Found {len(trades)} trades without confidence")
        return trades
        
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return []

def update_trade_confidence(db_path: str, trade_id: str, confidence: float) -> bool:
    """Actualizar confidence de un trade específico"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trades 
            SET confidence = ? 
            WHERE trade_id = ?
        """, (confidence, trade_id))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0
        
    except Exception as e:
        logger.error(f"Error updating confidence for {trade_id}: {e}")
        return False

def main():
    """Función principal"""
    db_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"
    
    logger.info("🚀 Iniciando cálculo de confidence para trades existentes...")
    
    # 1. Obtener trades sin confidence
    trades = get_trades_without_confidence(db_path)
    
    if not trades:
        logger.info("✅ Todos los trades ya tienen confidence asignado")
        return
    
    # 2. Calcular y actualizar confidence
    updated_count = 0
    failed_count = 0
    
    for trade in trades:
        try:
            # Calcular confidence
            confidence = calculate_enhanced_confidence(trade)
            
            # Actualizar en la base de datos
            if update_trade_confidence(db_path, trade['trade_id'], confidence):
                updated_count += 1
                logger.info(f"✅ {trade['symbol']} ({trade['trade_id'][:8]}): confidence = {confidence}%")
            else:
                failed_count += 1
                logger.error(f"❌ Error updating {trade['trade_id']}")
                
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ Error processing {trade.get('trade_id', 'unknown')}: {e}")
    
    # 3. Reporte final
    logger.info(f"""
    📊 REPORTE DE ACTUALIZACIÓN COMPLETADO:
    ✅ Trades actualizados: {updated_count}
    ❌ Trades fallidos: {failed_count}
    📈 Total procesados: {len(trades)}
    """)
    
    if updated_count > 0:
        logger.info("🔄 Ahora puedes ejecutar /tradetally_sync para sincronizar los datos de confidence")

if __name__ == "__main__":
    main()