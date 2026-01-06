#!/usr/bin/env python3
"""
Notification Filter - Sistema anti-spam para notificaciones de trading
=====================================================================

Evita spam de notificaciones aplicando filtros inteligentes:
- Cooldown de 5 minutos entre notificaciones del mismo símbolo
- Solo notifica cambios significativos (precio >5%, gap >2%, volumen >50%, score >1pt)
- Primera detección de un símbolo siempre notifica

Extraído de unified_main.py para reutilización en todo el sistema.

Author: Claude Code
Date: 2025-08-26
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging


class NotificationFilter:
    """
    Sistema anti-spam inteligente para notificaciones de trading
    
    Características:
    - Cooldown configurable entre notificaciones del mismo símbolo
    - Detección de cambios significativos en métricas clave
    - Logging detallado para debugging
    - Gestión automática de estado de notificaciones
    """
    
    def __init__(self, 
                 cooldown_seconds: int = 300,  # 5 minutos por defecto
                 logger: Optional[logging.Logger] = None):
        """
        Args:
            cooldown_seconds: Tiempo mínimo entre notificaciones del mismo símbolo
            logger: Logger opcional para debugging
        """
        self.notification_cooldown = cooldown_seconds
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # Cache de notificaciones: {symbol: {last_notified: datetime, last_data: dict}}
        self.notified_plays: Dict[str, Dict] = {}
        
        # Thresholds para cambios significativos
        self.thresholds = {
            'price_change': 0.05,      # 5% cambio de precio
            'gap_change': 0.02,        # 2% cambio de gap  
            'volume_change': 0.5,      # 50% cambio de volumen
            'score_change': 1.0        # 1 punto cambio de quality score
        }
        
        self.logger.info(f"🚫 NotificationFilter initialized (cooldown: {cooldown_seconds}s)")
    
    def should_notify(self, symbol: str, current_data: Dict) -> tuple[bool, str]:
        """
        Determinar si un símbolo merece notificación
        
        Args:
            symbol: Símbolo a evaluar
            current_data: Datos actuales del play {price, gap, volume_ratio, quality_score}
        
        Returns:
            (should_notify: bool, reason: str)
        """
        now = datetime.now()
        
        # Primera detección - siempre notificar
        if symbol not in self.notified_plays:
            self.notified_plays[symbol] = {
                'last_notified': now,
                'last_data': current_data.copy()
            }
            reason = "Nuevo símbolo detectado"
            self.logger.info(f"🆕 {reason}: {symbol}")
            return True, reason
        
        # Verificar cooldown
        last_notification = self.notified_plays[symbol]['last_notified']
        seconds_since_last = (now - last_notification).total_seconds()
        
        if seconds_since_last < self.notification_cooldown:
            remaining = self.notification_cooldown - seconds_since_last
            reason = f"En cooldown ({remaining:.0f}s restantes)"
            self.logger.debug(f"🔇 {symbol}: {reason}")
            return False, reason
        
        # Verificar cambios significativos
        last_data = self.notified_plays[symbol]['last_data']
        significant_changes = self._detect_significant_changes(current_data, last_data)
        
        if significant_changes:
            # Actualizar cache con nueva notificación
            self.notified_plays[symbol] = {
                'last_notified': now,
                'last_data': current_data.copy()
            }
            reason = f"Cambios significativos: {', '.join(significant_changes)}"
            self.logger.info(f"📊 {symbol}: {reason}")
            return True, reason
        else:
            # Actualizar solo los datos, no la fecha de notificación
            self.notified_plays[symbol]['last_data'] = current_data.copy()
            reason = "Sin cambios significativos"
            self.logger.debug(f"⚪ {symbol}: {reason}")
            return False, reason
    
    def _detect_significant_changes(self, current: Dict, last: Dict) -> List[str]:
        """Detectar cambios significativos entre datos actuales y anteriores"""
        changes = []
        
        # Cambio de precio > threshold
        if last.get('price', 0) > 0:
            price_change = abs(current.get('price', 0) - last['price']) / last['price']
            if price_change > self.thresholds['price_change']:
                changes.append(f"precio Δ{price_change*100:.1f}%")
        
        # Cambio de gap > threshold
        gap_change = abs(current.get('gap', 0) - last.get('gap', 0))
        if gap_change > self.thresholds['gap_change'] * 100:  # threshold está en decimal, gap en %
            changes.append(f"gap Δ{gap_change:.1f}%")
        
        # Cambio de volumen > threshold
        if last.get('volume_ratio', 0) > 0:
            vol_change = abs(current.get('volume_ratio', 0) - last['volume_ratio']) / max(last['volume_ratio'], 0.1)
            if vol_change > self.thresholds['volume_change']:
                changes.append(f"vol Δ{vol_change*100:.1f}%")
        
        # Cambio de quality score > threshold
        score_change = abs(current.get('quality_score', 0) - last.get('quality_score', 0))
        if score_change > self.thresholds['score_change']:
            changes.append(f"score Δ{score_change:.1f}pts")
        
        return changes
    
    def filter_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Filtrar lista completa de oportunidades
        
        Args:
            opportunities: Lista de oportunidades con formato {symbol, current_price, gap_percentage, ...}
        
        Returns:
            Lista filtrada de oportunidades que merecen notificación
        """
        worthy_plays = []
        
        for play in opportunities:
            symbol = play.get('symbol', '')
            if not symbol:
                continue
            
            current_data = {
                'price': play.get('current_price', 0),
                'gap': play.get('gap_percentage', 0),
                'volume_ratio': play.get('volume_ratio', 0),
                'quality_score': play.get('quality_score', 0)
            }
            
            should_notify, reason = self.should_notify(symbol, current_data)
            
            if should_notify:
                play['notification_reason'] = reason
                worthy_plays.append(play)
        
        if worthy_plays:
            symbols = [p.get('symbol') for p in worthy_plays]
            self.logger.info(f"📢 {len(worthy_plays)} plays merecen notificación: {symbols}")
        else:
            self.logger.debug("🔇 Ningún play merece notificación")
        
        return worthy_plays
    
    def get_notification_status(self) -> Dict:
        """Obtener estado actual del filtro para debugging"""
        now = datetime.now()
        status = {
            'total_symbols': len(self.notified_plays),
            'cooldown_seconds': self.notification_cooldown,
            'thresholds': self.thresholds,
            'symbols': {}
        }
        
        for symbol, data in self.notified_plays.items():
            time_since = (now - data['last_notified']).total_seconds()
            status['symbols'][symbol] = {
                'last_notified': data['last_notified'].strftime('%H:%M:%S'),
                'seconds_since_last': time_since,
                'in_cooldown': time_since < self.notification_cooldown,
                'last_data': data['last_data']
            }
        
        return status
    
    def clear_cache(self, symbol: str = None):
        """Limpiar cache de notificaciones"""
        if symbol:
            if symbol in self.notified_plays:
                del self.notified_plays[symbol]
                self.logger.info(f"🗑️ Cache limpio para {symbol}")
        else:
            self.notified_plays.clear()
            self.logger.info("🗑️ Todo el cache de notificaciones limpio")