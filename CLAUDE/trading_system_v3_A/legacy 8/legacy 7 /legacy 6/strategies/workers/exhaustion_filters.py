"""
Exhaustion Filters Module - Anti-Climax Filters for Workers

Este módulo proporciona filtros de "Agotamiento" (Exhaustion) reutilizables para evitar
compras en techos climáticos (Buying Climaxes) o extensiones parabólicas insostenibles.

Diferencia con TrendFilters:
- TrendFilters: Evita entrar CONTRA la tendencia (ej. comprar en bajada).
- ExhaustionFilters: Evita entrar AL FINAL de la tendencia (ej. comprar en el pico).

Patrones detectados:
1. Wick Rejection: Mechas superiores largas en máximos (rechazo de precios altos).
2. Parabolic Extension: Precio demasiado alejado de medias móviles (reversión a la media inminente).
3. Volume Churn: Volumen extremo sin progreso en precio (distribución oculta).

Uso:
    from strategies.workers.exhaustion_filters import ExhaustionFilters
    
    exhaustion = ExhaustionFilters(logger=self.logger)
    is_safe, reason = exhaustion.check_exhaustion(bars, current_price)
    
    if not is_safe:
        logger.info(f"⚪ {symbol}: REJECTED - {reason}")
        return False
"""

import logging
from typing import List, Tuple, Optional, Any
from core.td_sequential import TDSequentialDetector

class ExhaustionFilters:
    """
    Filtros anti-climax para workers
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None,
                 enable_wick: bool = True,
                 enable_extension: bool = True,
                 enable_churn: bool = True,
                 enable_demark: bool = False,
                 max_wick_pct: float = 0.40,      # Mecha > 40% del rango es rechazo
                 max_extension_pct: float = 0.15, # 15% alejado de EMA20 es parabólico
                 churn_vol_mult: float = 3.0,    # 3x volumen promedio es climático
                 demark_max_count: int = 9):      # TD Setup count threshold
                 
        self.logger = logger or logging.getLogger(__name__)
        self.enable_wick = enable_wick
        self.enable_extension = enable_extension
        self.enable_churn = enable_churn
        self.enable_demark = enable_demark
        
        self.max_wick_pct = max_wick_pct
        self.max_extension_pct = max_extension_pct
        self.churn_vol_mult = churn_vol_mult
        self.demark_max_count = demark_max_count
        
        # Initialize specialized detectors
        self.td_detector = TDSequentialDetector(setup_max=demark_max_count)

    def check_exhaustion(self, bars: List, current_price: float, 
                        surveillance_mode: bool = False) -> Tuple[bool, str]:
        """
        Verifica signos de agotamiento de compradores.
        
        Returns:
            Tuple (is_safe, reason)
            - is_safe=True: NO hay agotamiento (Safe to buy)
            - is_safe=False: SÍ hay agotamiento (Dangerous)
        """
        try:
            if not bars or len(bars) < 20:
                return True, "Insufficient data"

            current_bar = bars[-1]
            
            # ===== FILTRO 1: Wick Rejection (Rechazo de Precios Altos) =====
            # Detecta "Shooting Stars" o similares en la última vela
            if self.enable_wick:
                bar_range = current_bar.high - current_bar.low
                if bar_range > 0:
                    upper_wick = current_bar.high - max(current_bar.open, current_bar.close)
                    wick_pct = upper_wick / bar_range
                    
                    # Si la mecha superior es muy larga (>40-50% del rango total)
                    # Y el precio cierra en la mitad inferior
                    is_bearish_close = current_bar.close < (current_bar.high + current_bar.low) / 2
                    
                    if wick_pct > self.max_wick_pct and is_bearish_close:
                        msg = f"Wick Rejection (Upper wick {wick_pct:.0%} of range)"
                        if surveillance_mode:
                            self.logger.warning(f"⚠️ {msg}")
                        else:
                            return False, msg

            # ===== FILTRO 2: Parabolic Extension (Alejamiento de medias) =====
            # El precio no puede subir eternamente sin tocar la EMA20
            if self.enable_extension:
                ema20 = self._calculate_ema20(bars)
                if ema20 > 0:
                    dist_pct = (current_price - ema20) / ema20
                    
                    if dist_pct > self.max_extension_pct:
                        msg = f"Parabolic Extension ({dist_pct:.1%} > {self.max_extension_pct:.1%} from EMA20)"
                        if surveillance_mode:
                            # En vigilancia somos más flexibles porque TRAMAMOS el breakout
                            pass 
                        else:
                            return False, msg

            # ===== FILTRO 3: Volume Churn (Agotamiento por Volumen) =====
            # Mucho esfuerzo (volumen) para poco resultado (precio no sube)
            if self.enable_churn:
                avg_vol = sum(b.volume for b in bars[-10:]) / 10
                if avg_vol > 0:
                    vol_ratio = current_bar.volume / avg_vol
                    
                    # Si hay volumen climático (>3x) pero el cuerpo es pequeño (Doji/Spinning Top)
                    body_size = abs(current_bar.close - current_bar.open)
                    bar_range = current_bar.high - current_bar.low
                    
                    if bar_range > 0:
                        body_pct = body_size / bar_range
                        
                        # Volumen masivo + Cuerpo pequeño = Churning/Distribution
                        if vol_ratio > self.churn_vol_mult and body_pct < 0.3:
                            return False, f"Volume Churn (Vol {vol_ratio:.1f}x with tiny body)"

            # ===== FILTRO 4: DeMark Exhaustion (TD Sequential Setup) =====
            # Detecta agotamiento basado en secuencia de velas
            if self.enable_demark:
                report = self.td_detector.get_exhaustion_score(bars)
                if report['is_exhausted'] and report['direction'] == 'BULLISH':
                    return False, f"DeMark Exhaustion (Bullish Setup Count {report['setup_count']})"

            return True, "No exhaustion detected"

        except Exception as e:
            self.logger.error(f"Error in exhaustion filters: {e}")
            return True, "Error checking exhaustion"

    def _calculate_ema20(self, bars: List) -> float:
        """Calcula última EMA20 simple"""
        closes = [b.close for b in bars]
        if len(closes) < 20:
            return closes[-1] if closes else 0
            
        # Cálculo rápido EMA
        multiplier = 2 / (20 + 1)
        ema = sum(closes[:20]) / 20 # SMA inicial
        
        for price in closes[20:]:
            ema = (price - ema) * multiplier + ema
            
        return ema

def create_exhaustion_filters_from_config(config, section: str, logger: Optional[logging.Logger] = None) -> ExhaustionFilters:
    """Factory method para crear filtros desde config"""
    if config and hasattr(config, 'getboolean'):
         return ExhaustionFilters(
            logger=logger,
            enable_wick=config.getboolean(section, 'enable_wick_filter', fallback=True),
            enable_extension=config.getboolean(section, 'enable_extension_filter', fallback=True),
            enable_churn=config.getboolean(section, 'enable_churn_filter', fallback=True),
            enable_demark=config.getboolean(section, 'enable_demark_filter', fallback=False),
            max_wick_pct=config.getfloat(section, 'max_wick_pct', fallback=0.40),
            max_extension_pct=config.getfloat(section, 'max_extension_pct', fallback=0.15),
            demark_max_count=config.getint(section, 'demark_max_count', fallback=9)
        )
    return ExhaustionFilters(logger=logger)
