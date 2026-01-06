#!/usr/bin/env python3
"""
Universal Structural Exit Calculator

Sistema universal de cálculo de TP/SL para TODOS los workers basado en:
1. Niveles estructurales (soporte/resistencia)
2. Invalidación de patrones (ODS, Structure)
3. Expected Value (EV) filtering
4. R:R ratio validation

Filosofía:
- SL = Invalidación del pattern O soporte estructural (lo que sea más lógico)
- TP = Resistencia estructural (objetivo realista)
- EV = Filtro final para rechazar trades con EV negativo/bajo

Compatible con TODOS los workers:
- Daily Plays (usa ODS invalidation + resistance)
- ORB (usa OR low como SL, previous high como TP)
- MACDV (usa setup invalidation + resistance)
- Momentum Breakout (usa breakout level como SL)
- VCP (usa pivot como SL, measured move como TP)

Author: Trading System
Date: 2025-11-10
"""

import logging
from typing import Dict, Optional, Tuple, List
from enum import Enum


class ExitLevel(Enum):
    """Tipos de niveles para exits"""
    PATTERN_INVALIDATION = "pattern_invalidation"  # Invalidación del patrón
    SUPPORT = "support"  # Soporte técnico
    RESISTANCE = "resistance"  # Resistencia técnica
    ATR_BASED = "atr_based"  # Basado en volatilidad
    MEASURED_MOVE = "measured_move"  # Movimiento medido (VCP, C&H)
    PSYCHOLOGICAL = "psychological"  # Nivel psicológico (números redondos)


class TradingHorizon(Enum):
    """Trading horizon for timeframe-aware stop placement"""
    INTRADAY = "intraday"  # Same-day trades: use intraday supports only (LOD, VWAP, OR Low) - max 8% SL
    SWING_SHORT = "swing_short"  # 1-3 day trades: intraday + previous day supports - max 12% SL
    SWING = "swing"  # 3+ day trades: all supports including weekly - max 15% SL


class StructuralExitCalculator:
    """
    Calculadora universal de exits estructurales con Expected Value filtering
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        min_risk_reward: Optional[float] = None,
        min_expected_value: Optional[float] = None,
        resistance_buffer_pct: Optional[float] = None,
        support_buffer_pct: Optional[float] = None,
        strong_resistance_threshold: Optional[int] = None
    ):
        """
        Args:
            config: Config dict from config.ini (if available)
            min_risk_reward: R:R mínimo aceptable (override config)
            min_expected_value: EV mínimo en % (override config)
            resistance_buffer_pct: Buffer antes de resistencia para TP (override config)
            support_buffer_pct: Buffer después de soporte para SL (override config)
            strong_resistance_threshold: Mínimo strength para limitar TP (override config)
        """
        self.logger = logging.getLogger(__name__)

        # Read from config.ini if available, otherwise use defaults
        if config:
            # Handle different config object types (Dict, ConfigParser, ConfigManager)
            def get_config_val(key, default):
                # 1. Try dictionary access (most direct)
                if isinstance(config, dict):
                    return config.get(key, default)
                
                # 2. Try ConfigManager/ConfigParser interface (requires section)
                # We assume these parameters are in the [GLOBAL] section
                if hasattr(config, 'get'):
                    try:
                        # Try getting from GLOBAL section first
                        val = config.get('GLOBAL', key, fallback=default)
                        if val is not None:
                            return float(val) if isinstance(val, (int, float, str)) and str(val).replace('.','').isdigit() else val
                    except (TypeError, ValueError, AttributeError):
                        # Fallback for objects that have .get() but not compatible signature
                        pass
                        
                # 3. Try direct attribute access
                if hasattr(config, key):
                    return getattr(config, key)
                    
                return default

            self.min_risk_reward = float(get_config_val('min_risk_reward_ratio', 2.0))
            self.min_expected_value = float(get_config_val('min_expected_value_pct', 2.0))
            self.resistance_buffer = float(get_config_val('resistance_buffer_pct', 0.02))
            self.support_buffer = float(get_config_val('support_buffer_pct', 0.01))
            self.strong_resistance_threshold = int(get_config_val('strong_resistance_threshold', 70))
        else:
            # Default values
            self.min_risk_reward = 2.0
            self.min_expected_value = 2.0
            self.resistance_buffer = 0.02
            self.support_buffer = 0.01
            self.strong_resistance_threshold = 70

        # Allow override via parameters
        if min_risk_reward is not None:
            self.min_risk_reward = min_risk_reward
        if min_expected_value is not None:
            self.min_expected_value = min_expected_value
        if resistance_buffer_pct is not None:
            self.resistance_buffer = resistance_buffer_pct
        if support_buffer_pct is not None:
            self.support_buffer = support_buffer_pct
        if strong_resistance_threshold is not None:
            self.strong_resistance_threshold = strong_resistance_threshold

        self.logger.info(
            f"🎯 Structural Exit Calculator initialized - "
            f"Min R:R={self.min_risk_reward:.1f}, Min EV={self.min_expected_value:.1f}%, "
            f"Strong resistance threshold={self.strong_resistance_threshold}"
        )

    def calculate_exits(
        self,
        opportunity: Dict,
        trading_horizon: str = "SWING_SHORT"
    ) -> Optional[Dict]:
        """
        Calcula exits estructurales para una opportunity

        Args:
            opportunity: Dict con todos los datos del setup
            trading_horizon: Trading timeframe ('INTRADAY', 'SWING_SHORT', 'SWING')
                           Determines which support levels to use and max SL distance

        Returns:
            Dict con exits y validación O None si trade rechazado
            {
                'tp_price': float,
                'tp_pct': float,
                'tp_source': ExitLevel,
                'sl_price': float,
                'sl_pct': float,
                'sl_source': ExitLevel,
                'risk_reward': float,
                'expected_value_pct': float,
                'win_probability': float,
                'reasoning': List[str],
                'approved': bool
            }
        """
        try:
            entry_price = opportunity.get('current_price', 0)
            if entry_price <= 0:
                self.logger.error("Invalid entry price")
                return None

            symbol = opportunity.get('symbol', 'UNKNOWN')

            # 1. Detectar niveles estructurales (filtered by trading horizon)
            levels = self._detect_structural_levels(opportunity, trading_horizon)

            # 2. Calcular SL óptimo (prioridad a invalidación > soporte > ATR)
            sl_price, sl_source = self._calculate_optimal_sl(
                entry_price=entry_price,
                levels=levels,
                opportunity=opportunity
            )

            if sl_price is None:
                self.logger.warning(f"{symbol}: No se pudo calcular SL válido")
                return None

            # 3. Calcular TP óptimo (prioridad a resistencia > quality-based > R:R min)
            tp_price, tp_source = self._calculate_optimal_tp(
                entry_price=entry_price,
                sl_price=sl_price,
                levels=levels,
                opportunity=opportunity
            )

            if tp_price is None:
                self.logger.warning(f"{symbol}: No se pudo calcular TP válido")
                return None

            # 4. Calcular métricas
            risk_pct = abs((sl_price - entry_price) / entry_price) * 100
            reward_pct = abs((tp_price - entry_price) / entry_price) * 100
            risk_reward = reward_pct / risk_pct if risk_pct > 0 else 0

            # 5. Validar R:R mínimo
            if risk_reward < self.min_risk_reward:
                self.logger.info(
                    f"❌ {symbol}: R:R {risk_reward:.2f} < mínimo {self.min_risk_reward} "
                    f"(TP={reward_pct:.1f}%, SL={risk_pct:.1f}%)"
                )
                return {
                    'approved': False,
                    'rejection_reason': f'Low R:R ({risk_reward:.2f})',
                    'risk_reward': risk_reward
                }

            # 6. Calcular Expected Value
            ev_data = self._calculate_expected_value(
                entry_price=entry_price,
                tp_price=tp_price,
                sl_price=sl_price,
                levels=levels,
                opportunity=opportunity
            )

            # 7. Validar EV mínimo
            if ev_data['ev_pct'] < self.min_expected_value:
                self.logger.info(
                    f"❌ {symbol}: EV {ev_data['ev_pct']:.2f}% < mínimo {self.min_expected_value}% "
                    f"(Win prob={ev_data['win_prob']*100:.1f}%)"
                )
                return {
                    'approved': False,
                    'rejection_reason': f'Low EV ({ev_data["ev_pct"]:.2f}%)',
                    'expected_value_pct': ev_data['ev_pct'],
                    'win_probability': ev_data['win_prob']
                }

            # 8. Build reasoning
            reasoning = self._build_reasoning(
                entry_price=entry_price,
                tp_price=tp_price,
                tp_source=tp_source,
                sl_price=sl_price,
                sl_source=sl_source,
                risk_reward=risk_reward,
                ev_data=ev_data,
                levels=levels
            )

            # 9. Trade APROBADO
            self.logger.info(
                f"✅ {symbol}: APPROVED - TP=${tp_price:.2f} ({reward_pct:.1f}%), "
                f"SL=${sl_price:.2f} ({risk_pct:.1f}%), R:R={risk_reward:.2f}, "
                f"EV={ev_data['ev_pct']:.2f}%"
            )

            return {
                'tp_price': tp_price,
                'tp_pct': reward_pct,
                'tp_source': tp_source.value,
                'sl_price': sl_price,
                'sl_pct': risk_pct,
                'sl_source': sl_source.value,
                'risk_reward': risk_reward,
                'expected_value_pct': ev_data['ev_pct'],
                'win_probability': ev_data['win_prob'],
                'reasoning': reasoning,
                'approved': True
            }

        except Exception as e:
            self.logger.error(f"Error calculating exits: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def _detect_structural_levels(self, opportunity: Dict, trading_horizon: str = "SWING_SHORT") -> Dict:
        """
        Detecta todos los niveles estructurales relevantes con STRENGTH SCORING
        Filters supports based on trading_horizon to prevent excessive stop distances

        Args:
            opportunity: Opportunity data dict
            trading_horizon: 'INTRADAY', 'SWING_SHORT', or 'SWING'

        Returns:
            {
                'resistances': [(price, source, strength), ...],  # Sorted by strength DESC
                'supports': [(price, source, strength), ...],  # Filtered by horizon
                'invalidation': (price, source),
                'atr': float,
                'entry_price': float,
                'trading_horizon': str
            }

        Strength scoring (0-100):
        - 90-100: Resistencia FUERTE (previous day high, weekly high)
        - 70-89: Resistencia MEDIA (multiple touches, psychological)
        - 50-69: Resistencia DÉBIL (high of day, OR high)
        - < 50: Proyección/ATR (no es resistencia real)
        """
        entry_price = opportunity.get('current_price', 0)
        intraday_structure = opportunity.get('intraday_structure', {})
        ods_data = opportunity.get('ods_data', {})
        daily_potential = opportunity.get('daily_potential', {})

        # Helper function to safely get attributes from dict or dataclass
        def safe_get(obj, key, default=None):
            """Get value from dict or object attribute"""
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            else:
                # It's a dataclass or object with attributes
                return getattr(obj, key, default)

        resistances = []
        supports = []
        invalidation = None

        # === RESISTANCES (con strength scoring) ===

        # 1. Previous Day High - FUERTE (95)
        # Razón: Mayor temporalidad, confirmado por mercado completo
        prev_high = safe_get(daily_potential, 'previous_high')
        if prev_high and prev_high > entry_price:
            resistances.append((prev_high, ExitLevel.RESISTANCE, 95))

        # 2. Weekly/Monthly High - MUY FUERTE (100)
        weekly_high = safe_get(daily_potential, 'weekly_high')
        if weekly_high and weekly_high > entry_price:
            resistances.append((weekly_high, ExitLevel.RESISTANCE, 100))

        # 3. Psychological Level (números redondos) - MEDIA (75)
        # Razón: Psicología del mercado, múltiples traders ponen órdenes ahí
        psych_resistance = self._next_psychological_level(entry_price)
        if psych_resistance > entry_price:
            resistances.append((psych_resistance, ExitLevel.PSYCHOLOGICAL, 75))

        # 4. High of Day - DÉBIL (60)
        # Razón: Solo intraday, puede romperse fácilmente
        hod = safe_get(intraday_structure, 'high_of_day')
        if hod and hod > entry_price:
            resistances.append((hod, ExitLevel.RESISTANCE, 60))

        # 5. Opening Range High - DÉBIL (55)
        or_high = safe_get(intraday_structure, 'opening_range_high')
        if or_high and or_high > entry_price:
            resistances.append((or_high, ExitLevel.RESISTANCE, 55))

        # 6. Measured move target - MEDIA (70)
        # Razón: Pattern-based, tiene lógica estructural
        measured_target = opportunity.get('measured_move_target')
        if measured_target and measured_target > entry_price:
            resistances.append((measured_target, ExitLevel.MEASURED_MOVE, 70))

        # 7. ATR-based target - PROYECCIÓN (40)
        # Razón: No es resistencia real, solo proyección estadística
        atr = opportunity.get('atr', entry_price * 0.02)
        atr_target = entry_price + (atr * 2.5)
        resistances.append((atr_target, ExitLevel.ATR_BASED, 40))

        # === SUPPORTS (con strength scoring) ===

        # 1. Previous Day Low - FUERTE (95)
        prev_low = safe_get(daily_potential, 'previous_low')
        if prev_low and prev_low < entry_price:
            supports.append((prev_low, ExitLevel.SUPPORT, 95))

        # 2. Weekly Low - MUY FUERTE (100)
        weekly_low = safe_get(daily_potential, 'weekly_low')
        if weekly_low and weekly_low < entry_price:
            supports.append((weekly_low, ExitLevel.SUPPORT, 100))

        # 3. Low of Day - DÉBIL (60)
        lod = safe_get(intraday_structure, 'low_of_day')
        if lod and lod < entry_price:
            supports.append((lod, ExitLevel.SUPPORT, 60))

        # 4. Opening Range Low - DÉBIL (55)
        or_low = safe_get(intraday_structure, 'opening_range_low')
        if or_low and or_low < entry_price:
            supports.append((or_low, ExitLevel.SUPPORT, 55))

        # 5. VWAP - MEDIA (70)
        # Razón: Usado por institucionales, puede actuar como soporte fuerte
        vwap = safe_get(intraday_structure, 'vwap')
        if vwap and vwap < entry_price:
            supports.append((vwap, ExitLevel.SUPPORT, 70))

        # 6. ATR-based support - PROYECCIÓN (40)
        atr_support = entry_price - (atr * 1.5)
        supports.append((atr_support, ExitLevel.ATR_BASED, 40))

        # === INVALIDATION ===

        # Pattern invalidation (priority)
        invalid_price = opportunity.get('invalid_price')
        if invalid_price:
            invalidation = (invalid_price, ExitLevel.PATTERN_INVALIDATION)
        # ODS invalidation
        elif safe_get(ods_data, 'invalidation_price'):
            invalidation = (safe_get(ods_data, 'invalidation_price'), ExitLevel.PATTERN_INVALIDATION)
        # Structure invalidation
        elif safe_get(intraday_structure, 'invalidation_level'):
            invalidation = (safe_get(intraday_structure, 'invalidation_level'), ExitLevel.PATTERN_INVALIDATION)

        # === FILTER SUPPORTS BY TRADING HORIZON ===
        # This prevents using distant multi-day supports for intraday trades
        
        if trading_horizon == "INTRADAY":
            # INTRADAY: Only use intraday supports (LOD, OR Low, VWAP, ATR)
            # Exclude: Previous Day Low (95), Weekly Low (100)
            supports = [
                (price, source, strength) 
                for price, source, strength in supports 
                if strength < 90  # Filter out Previous Day Low (95) and Weekly Low (100)
            ]
            self.logger.debug(f"INTRADAY horizon: filtered to {len(supports)} intraday supports")
            
        elif trading_horizon == "SWING_SHORT":
            # SWING_SHORT: Use intraday + previous day supports
            # Exclude: Weekly Low (100)
            supports = [
                (price, source, strength) 
                for price, source, strength in supports 
                if strength < 100  # Filter out Weekly Low (100)
            ]
            self.logger.debug(f"SWING_SHORT horizon: filtered to {len(supports)} supports (intraday + prev day)")
            
        # SWING: Use all supports (no filtering)
        # This is the default behavior for multi-day swing trades

        # CRITICAL: Sort resistances by STRENGTH (DESC), then by proximity
        # Esto asegura que resistencias FUERTES se priorizan sobre DÉBILES
        resistances.sort(key=lambda x: (-x[2], x[0]))  # Strength DESC, Price ASC

        # CRITICAL: For INTRADAY/SWING_SHORT, prioritize PROXIMITY over strength
        # For SWING, keep original behavior (strength first)
        if trading_horizon in ["INTRADAY", "SWING_SHORT"]:
            # Sort by proximity first (closest to entry), then strength
            supports.sort(key=lambda x: (-x[0], -x[2]))  # Price DESC (closest first), then Strength DESC
        else:
            # SWING: Original behavior - strength first
            supports.sort(key=lambda x: (-x[2], -x[0]))  # Strength DESC, Price DESC (closest first)

        return {
            'resistances': resistances,
            'supports': supports,
            'invalidation': invalidation,
            'atr': atr,
            'entry_price': entry_price,
            'trading_horizon': trading_horizon
        }

    def _calculate_optimal_sl(
        self,
        entry_price: float,
        levels: Dict,
        opportunity: Dict
    ) -> Tuple[Optional[float], Optional[ExitLevel]]:
        """
        Calcula SL óptimo con prioridades:
        1. Pattern invalidation
        2. Nearest support (con buffer)
        3. ATR-based
        
        Enforces max SL distance based on trading_horizon:
        - INTRADAY: max 8% SL
        - SWING_SHORT: max 12% SL
        - SWING: max 15% SL
        """
        # Get max SL distance based on trading horizon
        trading_horizon = levels.get('trading_horizon', 'SWING_SHORT')
        if trading_horizon == "INTRADAY":
            max_sl_pct = 8.0
        elif trading_horizon == "SWING_SHORT":
            max_sl_pct = 12.0
        else:  # SWING
            max_sl_pct = 15.0
        
        # PRIORITY 1: Pattern invalidation
        if levels['invalidation']:
            invalid_price, source = levels['invalidation']
            if invalid_price < entry_price:
                # Add buffer (1% below invalidation)
                sl_price = invalid_price * (1 - self.support_buffer)

                # Validate not too far (max based on horizon)
                sl_distance_pct = abs((sl_price - entry_price) / entry_price) * 100
                if sl_distance_pct <= max_sl_pct:
                    return sl_price, source
                else:
                    self.logger.debug(
                        f"Pattern invalidation SL too far ({sl_distance_pct:.1f}% > {max_sl_pct}% max for {trading_horizon})"
                    )

        # PRIORITY 2: Nearest support
        if levels['supports']:
            nearest_support, source, strength = levels['supports'][0]  # Closest to entry
            # Add buffer below support
            sl_price = nearest_support * (1 - self.support_buffer)

            # Validate reasonable distance (2% min, max based on horizon)
            sl_distance_pct = abs((sl_price - entry_price) / entry_price) * 100
            if 2.0 <= sl_distance_pct <= max_sl_pct:
                return sl_price, source
            elif sl_distance_pct > max_sl_pct:
                self.logger.debug(
                    f"Nearest support SL too far ({sl_distance_pct:.1f}% > {max_sl_pct}% max for {trading_horizon})"
                )

        # PRIORITY 3: ATR-based (fallback)
        atr = levels['atr']
        sl_price = entry_price - (atr * 1.5)

        # Validate
        sl_distance_pct = abs((sl_price - entry_price) / entry_price) * 100
        if 2.0 <= sl_distance_pct <= max_sl_pct:
            return sl_price, ExitLevel.ATR_BASED

        # LAST RESORT: Fixed percentage based on horizon
        if trading_horizon == "INTRADAY":
            fallback_pct = 0.05  # 5% for intraday
        elif trading_horizon == "SWING_SHORT":
            fallback_pct = 0.06  # 6% for swing short
        else:
            fallback_pct = 0.07  # 7% for swing
            
        sl_price = entry_price * (1 - fallback_pct)
        self.logger.debug(f"Using fallback SL: {fallback_pct*100:.0f}% for {trading_horizon}")
        return sl_price, ExitLevel.ATR_BASED

    def _calculate_optimal_tp(
        self,
        entry_price: float,
        sl_price: float,
        levels: Dict,
        opportunity: Dict
    ) -> Tuple[Optional[float], Optional[ExitLevel]]:
        """
        Calcula TP óptimo con PRIORIZACIÓN DE RESISTENCIAS FUERTES

        Lógica CRÍTICA:
        1. IGNORA resistencias DÉBILES (strength < 70) si están muy cercanas
        2. USA resistencias FUERTES (strength >= 70) como límite real
        3. Si no hay resistencias fuertes cercanas, usa quality-based target
        4. Fallback: Minimum R:R (3:1 de SL)

        Esto permite aprovechar "grandes corridas" sin limitarse por HOD intraday
        """
        risk = abs(entry_price - sl_price)

        # PRIORITY 1: Resistencias FUERTES (strength >= threshold from config)
        # Filtra resistencias débiles que limitarían el TP innecesariamente
        strong_resistances = [
            (price, source, strength)
            for price, source, strength in levels['resistances']
            if strength >= self.strong_resistance_threshold  # Configurable desde config.ini
        ]

        if strong_resistances:
            # Buscar primera resistencia FUERTE que dé buen R:R
            for resistance_price, source, strength in strong_resistances:
                # Buffer antes de resistencia
                tp_price = resistance_price * (1 - self.resistance_buffer)

                if tp_price <= entry_price:
                    continue

                reward = tp_price - entry_price
                rr = reward / risk if risk > 0 else 0

                # Si esta resistencia FUERTE da buen R:R, usarla
                if rr >= self.min_risk_reward:
                    self.logger.debug(
                        f"TP set at STRONG resistance (strength={strength}): "
                        f"${resistance_price:.2f}"
                    )
                    return tp_price, source

        # PRIORITY 2: Quality-based target (NO hay resistencia fuerte cercana)
        # Esto permite "grandes corridas" en setups A+
        quality_score = opportunity.get('quality_score', 50)
        if quality_score >= 75:
            # High quality = allow higher targets even without resistance
            if quality_score >= 85:
                quality_multiplier = 3.0  # A+: 3x risk
            else:
                quality_multiplier = 2.5  # A: 2.5x risk

            tp_price = entry_price + (risk * quality_multiplier)
            return tp_price, ExitLevel.ATR_BASED

        # PRIORITY 3: Minimum R:R (fallback)
        min_rr_multiplier = 3.0  # At least 3:1
        tp_price = entry_price + (risk * min_rr_multiplier)
        return tp_price, ExitLevel.ATR_BASED

    def _calculate_expected_value(
        self,
        entry_price: float,
        tp_price: float,
        sl_price: float,
        levels: Dict,
        opportunity: Dict
    ) -> Dict:
        """
        Calcula Expected Value basado en:
        - Distancia a resistencia (más cerca = mayor win prob)
        - Quality score
        - ODS strength
        - Histórico (si disponible en futuro)

        Returns:
            {
                'ev_pct': float,
                'win_prob': float,
                'avg_win': float,
                'avg_loss': float
            }
        """
        risk_pct = abs((sl_price - entry_price) / entry_price)
        reward_pct = abs((tp_price - entry_price) / entry_price)

        # BASE WIN PROBABILITY from resistance distance AND strength
        if levels['resistances']:
            # Buscar resistencia MÁS FUERTE (no necesariamente la más cercana)
            strongest_resistance = max(levels['resistances'], key=lambda x: x[2])
            nearest_resistance_price, nearest_source, nearest_strength = strongest_resistance

            distance_to_resistance = (nearest_resistance_price - entry_price) / entry_price
            tp_distance = (tp_price - entry_price) / entry_price

            # TP vs resistencia ratio
            tp_vs_resistance_ratio = tp_distance / distance_to_resistance if distance_to_resistance > 0 else 1

            # Base probability ajustada por strength de resistencia
            if nearest_strength >= 90:  # Resistencia MUY FUERTE
                # Win prob más conservador
                if tp_vs_resistance_ratio < 0.8:
                    base_win_prob = 0.75  # TP bien antes de resistencia fuerte
                elif tp_vs_resistance_ratio < 1.0:
                    base_win_prob = 0.55  # TP cerca de resistencia fuerte
                else:
                    base_win_prob = 0.35  # TP más allá de resistencia fuerte (difícil)
            elif nearest_strength >= 70:  # Resistencia MEDIA
                if tp_vs_resistance_ratio < 0.8:
                    base_win_prob = 0.70
                elif tp_vs_resistance_ratio < 1.0:
                    base_win_prob = 0.60
                else:
                    base_win_prob = 0.45
            else:  # Resistencia DÉBIL (< 70)
                # Más optimista porque puede romperse
                if tp_vs_resistance_ratio < 0.8:
                    base_win_prob = 0.65
                elif tp_vs_resistance_ratio < 1.0:
                    base_win_prob = 0.58
                else:
                    base_win_prob = 0.50  # Puede romper resistencia débil
        else:
            base_win_prob = 0.55  # No resistance detected

        # ADJUST for quality score
        quality_score = opportunity.get('quality_score', 50)
        if quality_score >= 85:
            quality_boost = 0.10
        elif quality_score >= 75:
            quality_boost = 0.05
        elif quality_score >= 65:
            quality_boost = 0.02
        else:
            quality_boost = -0.05

        # Helper function to safely get values from dict or object
        def safe_get(obj, attr, default=None):
            """Get attribute from dict or object"""
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(attr, default)
            else:
                return getattr(obj, attr, default)

        # ADJUST for ODS strength
        ods_data = opportunity.get('ods_data', {})
        ods_strength = safe_get(ods_data, 'strength', 0)
        if ods_strength >= 0.85:
            ods_boost = 0.05
        elif ods_strength >= 0.70:
            ods_boost = 0.02
        else:
            ods_boost = 0

        # FINAL win probability
        win_prob = min(0.85, base_win_prob + quality_boost + ods_boost)
        loss_prob = 1 - win_prob

        # Expected Value
        ev_pct = (win_prob * reward_pct - loss_prob * risk_pct) * 100

        return {
            'ev_pct': ev_pct,
            'win_prob': win_prob,
            'avg_win': reward_pct,
            'avg_loss': risk_pct
        }

    def _next_psychological_level(self, price: float) -> float:
        """Encuentra siguiente nivel psicológico (número redondo)"""
        if price < 5:
            return (int(price / 0.5) + 1) * 0.5
        elif price < 20:
            return (int(price / 5) + 1) * 5
        elif price < 100:
            return (int(price / 10) + 1) * 10
        else:
            return (int(price / 50) + 1) * 50

    def _build_reasoning(
        self,
        entry_price: float,
        tp_price: float,
        tp_source: ExitLevel,
        sl_price: float,
        sl_source: ExitLevel,
        risk_reward: float,
        ev_data: Dict,
        levels: Dict
    ) -> List[str]:
        """Build human-readable reasoning"""
        reasons = []

        # SL reasoning
        sl_pct = abs((sl_price - entry_price) / entry_price) * 100
        if sl_source == ExitLevel.PATTERN_INVALIDATION:
            reasons.append(f"🎯 SL: ${sl_price:.2f} ({sl_pct:.1f}%) - Pattern invalidation")
        elif sl_source == ExitLevel.SUPPORT:
            reasons.append(f"🎯 SL: ${sl_price:.2f} ({sl_pct:.1f}%) - Below support")
        else:
            reasons.append(f"🎯 SL: ${sl_price:.2f} ({sl_pct:.1f}%) - ATR-based")

        # TP reasoning
        tp_pct = abs((tp_price - entry_price) / entry_price) * 100
        if tp_source == ExitLevel.RESISTANCE:
            reasons.append(f"🎯 TP: ${tp_price:.2f} ({tp_pct:.1f}%) - Before resistance")
        elif tp_source == ExitLevel.MEASURED_MOVE:
            reasons.append(f"🎯 TP: ${tp_price:.2f} ({tp_pct:.1f}%) - Measured move")
        else:
            reasons.append(f"🎯 TP: ${tp_price:.2f} ({tp_pct:.1f}%) - Quality-based")

        # R:R
        if risk_reward >= 3.0:
            reasons.append(f"✅ Excellent R:R: {risk_reward:.2f}:1")
        elif risk_reward >= 2.0:
            reasons.append(f"✅ Good R:R: {risk_reward:.2f}:1")
        else:
            reasons.append(f"⚠️  Acceptable R:R: {risk_reward:.2f}:1")

        # Expected Value
        reasons.append(
            f"💰 EV: {ev_data['ev_pct']:.2f}% (Win prob: {ev_data['win_prob']*100:.1f}%)"
        )

        return reasons


# Singleton instance
_structural_exit_calculator = None
_structural_exit_calculator_config = None

def get_structural_exit_calculator(config: Optional[Dict] = None, force_reload: bool = False) -> StructuralExitCalculator:
    """
    Get singleton instance with config from config.ini

    Args:
        config: Config dict with structural exit parameters (optional)
        force_reload: Force recreation of singleton (for testing)

    Returns:
        StructuralExitCalculator instance
    """
    global _structural_exit_calculator, _structural_exit_calculator_config

    # Recreate if:
    # 1. Never created (None)
    # 2. Force reload requested
    # 3. Config changed (different config dict)
    if (_structural_exit_calculator is None or
        force_reload or
        (config is not None and config != _structural_exit_calculator_config)):

        _structural_exit_calculator = StructuralExitCalculator(config=config)
        _structural_exit_calculator_config = config

    return _structural_exit_calculator
