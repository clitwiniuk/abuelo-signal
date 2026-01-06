#!/usr/bin/env python3
"""
Trading Feedback Hook - Conecta trades reales con continuous learning
Se ejecuta cuando se abren/cierran trades para alimentar el ML
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, Optional
import json

from core.continuous_learning_engine import get_global_learning_engine, TradeResult

class TradingFeedbackHook:
    """
    Hook que captura trades y genera feedback para continuous learning
    """
    
    def __init__(self, trading_db_path: str = "trading_data.db"):
        self.trading_db_path = trading_db_path
        self.logger = logging.getLogger(__name__)
        self.learning_engine = get_global_learning_engine()
        
        # Cache para datos de entrada (volumen usado al abrir trade)
        self.trade_entry_cache = {}  # trade_id -> entry_data
        
    def on_trade_opened(self, trade_data: Dict):
        """
        Se ejecuta cuando se abre un trade
        Guarda los datos de volumen/contexto para posterior feedback
        """
        try:
            trade_id = trade_data.get('trade_id')
            symbol = trade_data.get('symbol')
            strategy = trade_data.get('strategy')
            
            if not all([trade_id, symbol, strategy]):
                self.logger.warning("⚠️ Incomplete trade data for feedback hook")
                return
            
            # Obtener contexto de volumen del trade
            volume_context = self._extract_volume_context(trade_data)
            
            # Guardar en cache para cuando se cierre el trade
            self.trade_entry_cache[trade_id] = {
                'symbol': symbol,
                'strategy': strategy,
                'volume_requirement_used': volume_context.get('requirement_used', 1.0),
                'actual_volume_ratio': volume_context.get('actual_volume', 1.0),
                'market_context': volume_context.get('market_context', {}),
                'entry_time': datetime.now(),
                'entry_price': trade_data.get('entry_price', 0.0)
            }
            
            self.logger.debug(
                f"📝 Cached trade entry data: {trade_id} | {symbol} | {strategy}"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error in on_trade_opened hook: {e}")
    
    def on_trade_closed(self, trade_data: Dict):
        """
        Se ejecuta cuando se cierra un trade
        Genera feedback para continuous learning
        """
        try:
            trade_id = trade_data.get('trade_id')
            pnl = trade_data.get('pnl', 0.0)
            exit_time = datetime.now()
            
            if trade_id not in self.trade_entry_cache:
                self.logger.warning(f"⚠️ No entry data cached for trade {trade_id}")
                return
            
            entry_data = self.trade_entry_cache[trade_id]
            
            # Calcular métricas de éxito
            duration_minutes = self._calculate_duration(entry_data['entry_time'], exit_time)
            success = self._determine_trade_success(pnl, duration_minutes, entry_data['strategy'])
            
            # Crear TradeResult para feedback
            trade_result = TradeResult(
                trade_id=trade_id,
                symbol=entry_data['symbol'],
                strategy=entry_data['strategy'],
                volume_requirement_used=entry_data['volume_requirement_used'],
                actual_volume_ratio=entry_data['actual_volume_ratio'],
                pnl=pnl,
                success=success,
                duration_minutes=duration_minutes,
                entry_time=entry_data['entry_time'],
                market_context=entry_data['market_context']
            )
            
            # Enviar feedback al continuous learning engine
            self.learning_engine.record_volume_decision_feedback(trade_result)
            
            # Limpiar cache
            del self.trade_entry_cache[trade_id]
            
            self.logger.info(
                f"📊 Trade feedback recorded: {trade_id} | "
                f"PnL: ${pnl:.2f} | Success: {success} | "
                f"Duration: {duration_minutes}min"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error in on_trade_closed hook: {e}")
    
    def _extract_volume_context(self, trade_data: Dict) -> Dict:
        """Extrae contexto de volumen del trade"""
        try:
            # Buscar datos de volumen en trading_data.db
            with sqlite3.connect(self.trading_db_path) as conn:
                # Si tenemos advanced_trading_results, usar esos datos
                cursor = conn.execute("""
                    SELECT daily_volume_context, intraday_volume_context, market_context
                    FROM advanced_trading_results
                    WHERE trade_id = ?
                """, (trade_data.get('trade_id'),))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'requirement_used': self._parse_volume_requirement(result[0], result[1]),
                        'actual_volume': self._parse_actual_volume(result[1]),
                        'market_context': self._parse_market_context(result[2])
                    }
            
            # Fallback: usar datos básicos del trade
            return {
                'requirement_used': 1.5,  # Default requirement
                'actual_volume': 1.0,     # Default volume ratio
                'market_context': {
                    'symbol': trade_data.get('symbol'),
                    'price': trade_data.get('entry_price', 0),
                    'strategy': trade_data.get('strategy')
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting volume context: {e}")
            return {'requirement_used': 1.5, 'actual_volume': 1.0, 'market_context': {}}
    
    def _parse_volume_requirement(self, daily_context: str, intraday_context: str) -> float:
        """Parse volume requirement from context strings"""
        try:
            # Look for patterns like "requirement: 1.2x" in context
            for context in [daily_context, intraday_context]:
                if context and "requirement:" in str(context).lower():
                    # Extract number after "requirement:"
                    parts = str(context).lower().split("requirement:")
                    if len(parts) > 1:
                        req_part = parts[1].split()[0].replace('x', '')
                        return float(req_part)
            return 1.5  # Default
        except:
            return 1.5
    
    def _parse_actual_volume(self, intraday_context: str) -> float:
        """Parse actual volume ratio from context"""
        try:
            if intraday_context and "volume" in str(intraday_context).lower():
                # Look for patterns like "2.3x volume" or "volume: 2.3x"
                context_str = str(intraday_context).lower()
                
                # Try different patterns
                for pattern in ["volume: ", "vol: "]:
                    if pattern in context_str:
                        start = context_str.find(pattern) + len(pattern)
                        vol_part = context_str[start:start+10].split()[0].replace('x', '')
                        return float(vol_part)
                        
            return 1.0  # Default
        except:
            return 1.0
    
    def _parse_market_context(self, market_context: str) -> Dict:
        """Parse market context into structured data"""
        try:
            return {
                'raw_context': str(market_context) if market_context else "",
                'parsed_time': datetime.now().isoformat()
            }
        except:
            return {}
    
    def _calculate_duration(self, entry_time: datetime, exit_time: datetime) -> int:
        """Calcula duración del trade en minutos"""
        try:
            return int((exit_time - entry_time).total_seconds() / 60)
        except:
            return 0
    
    def _determine_trade_success(self, pnl: float, duration_minutes: int, strategy: str) -> bool:
        """
        Determina si un trade fue exitoso basado en múltiples criterios
        No solo PnL, sino también duración y contexto de estrategia
        """
        try:
            # Criterio básico: PnL positivo
            if pnl > 0:
                return True
            
            # Criterios específicos por estrategia
            if strategy in ['macdv_smallcaps', 'daily_plays']:
                # Para estrategias intraday, pérdidas pequeñas + duración corta pueden ser aceptables
                if pnl >= -5.0 and duration_minutes <= 30:  # Loss < $5 and < 30min
                    return True
            
            elif strategy in ['gap_go', 'volume_breakout']:
                # Para estrategias de momentum, pérdidas rápidas son preferibles a holds largos
                if pnl >= -10.0 and duration_minutes <= 15:  # Quick exit with small loss
                    return True
            
            return False  # Default: unsuccessful
            
        except Exception as e:
            self.logger.error(f"❌ Error determining trade success: {e}")
            return pnl > 0  # Fallback to simple PnL check

# Global hook instance
_global_feedback_hook = None

def get_global_feedback_hook() -> TradingFeedbackHook:
    """Obtiene instancia global del feedback hook"""
    global _global_feedback_hook
    if _global_feedback_hook is None:
        _global_feedback_hook = TradingFeedbackHook()
    return _global_feedback_hook

# Convenience functions para usar desde el sistema de trading
def notify_trade_opened(trade_data: Dict):
    """Notifica que se abrió un trade"""
    hook = get_global_feedback_hook()
    hook.on_trade_opened(trade_data)

def notify_trade_closed(trade_data: Dict):
    """Notifica que se cerró un trade"""
    hook = get_global_feedback_hook()
    hook.on_trade_closed(trade_data)