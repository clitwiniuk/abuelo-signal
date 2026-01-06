"""
Adaptive Threshold Manager
===========================
Ajusta dinámicamente los umbrales de entrada de workers según régimen de mercado

Arquitectura:
- Singleton compartido por todos los workers
- Lee régimen de MarketRegimeDetector
- Proporciona thresholds adaptados en tiempo real
- NO modifica código de workers, solo overrides valores

Ejemplo de uso en workers:
    threshold_mgr = get_adaptive_threshold_manager()
    vwap_tolerance = threshold_mgr.get_vwap_tolerance()  # Auto-ajustado por régimen
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass

from core.market_regime_detector import (
    get_market_regime_detector,
    MarketRegime,
    MarketConditions
)


@dataclass
class WorkerThresholds:
    """Thresholds adaptativos para workers"""
    # VWAP thresholds
    vwap_price_tolerance_pct: float  # % below VWAP allowed
    vwap_trend_tolerance_pct: float  # Max VWAP decline allowed

    # Pattern completion thresholds
    min_pattern_completion: float  # Minimum pattern % to enter
    max_pattern_completion: float  # Maximum pattern % (too late)

    # Quality thresholds
    min_quality_score: float  # Minimum opportunity quality

    # Volume thresholds
    min_volume_ratio: float  # Minimum volume vs average

    # Divergence/MACD thresholds (for MACDV worker)
    min_divergence_strength: float  # 0-100

    # Risk adjustments
    position_size_multiplier: float  # Adjust position sizes
    max_daily_trades_multiplier: float  # Adjust daily trade limits

    # Entry gates
    allow_entries: bool  # Master switch for entries


class AdaptiveThresholdManager:
    """
    Singleton manager for adaptive worker thresholds

    Adjusts thresholds based on market regime automatically
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = logging.getLogger("AdaptiveThresholds")

        # Market regime detector reference
        self.regime_detector = get_market_regime_detector()

        # Default thresholds (baseline)
        self.baseline_thresholds = WorkerThresholds(
            vwap_price_tolerance_pct=2.0,
            vwap_trend_tolerance_pct=0.0,
            min_pattern_completion=25.0,
            max_pattern_completion=95.0,
            min_quality_score=50.0,
            min_volume_ratio=1.0,
            min_divergence_strength=30.0,
            position_size_multiplier=1.0,
            max_daily_trades_multiplier=1.0,
            allow_entries=True
        )

        # Cache for current thresholds
        self._cached_thresholds: Optional[WorkerThresholds] = None
        self._last_regime: Optional[MarketRegime] = None

        self._initialized = True
        self.logger.info("🎚️ Adaptive Threshold Manager initialized")

    def get_thresholds(self, force_update: bool = False, opportunity: Optional[Dict] = None) -> WorkerThresholds:
        """
        Get adaptive thresholds based on current market regime + opportunity context

        SMALLCAP-AWARE: Considers individual ticker catalyst/volume to override SPY regime

        Args:
            force_update: Force recalculation even if cached
            opportunity: Optional opportunity dict with catalyst_type, volume_ratio, quality_score

        Returns:
            WorkerThresholds adapted to current market conditions + ticker context
        """
        # Get current regime
        conditions = self.regime_detector.get_current_regime()

        if not conditions:
            self.logger.warning("⚠️ No market conditions - using baseline thresholds")
            return self.baseline_thresholds

        # Check if regime changed (invalidate cache)
        if self._last_regime != conditions.regime or force_update:
            self._cached_thresholds = self._calculate_adaptive_thresholds(conditions)
            self._last_regime = conditions.regime

            self.logger.info(
                f"🎚️ Thresholds adapted for {conditions.regime.value.upper()} regime"
            )

        # SMALLCAP OVERRIDE: If opportunity has strong catalyst, relax thresholds
        if opportunity:
            return self._apply_catalyst_override(self._cached_thresholds, conditions, opportunity)

        return self._cached_thresholds

    def _calculate_adaptive_thresholds(self, conditions: MarketConditions) -> WorkerThresholds:
        """
        Calculate adaptive thresholds based on market regime

        Logic:
        - BULL_HIGH_LIQUIDITY: Relajar criterios (más oportunidades)
        - BEAR_HIGH_VOL: Endurecer criterios (muy selectivo)
        - PANIC: Desactivar entradas
        - Etc.
        """
        regime = conditions.regime
        risk_factor = conditions.get_risk_adjustment_factor()

        # Start with baseline
        thresholds = WorkerThresholds(
            vwap_price_tolerance_pct=self.baseline_thresholds.vwap_price_tolerance_pct,
            vwap_trend_tolerance_pct=self.baseline_thresholds.vwap_trend_tolerance_pct,
            min_pattern_completion=self.baseline_thresholds.min_pattern_completion,
            max_pattern_completion=self.baseline_thresholds.max_pattern_completion,
            min_quality_score=self.baseline_thresholds.min_quality_score,
            min_volume_ratio=self.baseline_thresholds.min_volume_ratio,
            min_divergence_strength=self.baseline_thresholds.min_divergence_strength,
            position_size_multiplier=risk_factor,
            max_daily_trades_multiplier=1.0,
            allow_entries=True
        )

        # === REGIME-SPECIFIC ADJUSTMENTS ===

        if regime == MarketRegime.PANIC:
            # PANIC: Desactivar todas las entradas
            thresholds.allow_entries = False
            self.logger.warning("🚨 PANIC MODE: Entries DISABLED")

        elif regime == MarketRegime.BEAR_HIGH_VOL:
            # BEAR HIGH VOL: Muy conservador, solo setups perfectos
            thresholds.vwap_price_tolerance_pct = 1.0  # Muy estricto
            thresholds.vwap_trend_tolerance_pct = 0.0  # VWAP debe subir
            thresholds.min_pattern_completion = 40.0  # Patrones más desarrollados
            thresholds.min_quality_score = 70.0  # Solo alta calidad
            thresholds.min_volume_ratio = 1.5  # Volumen confirmado
            thresholds.min_divergence_strength = 50.0  # Divergencias fuertes
            thresholds.max_daily_trades_multiplier = 0.5  # Reducir trades
            self.logger.warning(
                "🐻 BEAR HIGH VOL: Thresholds tightened significantly"
            )

        elif regime == MarketRegime.BEAR_LOW_VOL:
            # BEAR LOW VOL: Conservador pero no extremo
            thresholds.vwap_price_tolerance_pct = 1.5
            thresholds.vwap_trend_tolerance_pct = -0.1
            thresholds.min_pattern_completion = 30.0
            thresholds.min_quality_score = 60.0
            thresholds.min_volume_ratio = 1.2
            thresholds.min_divergence_strength = 40.0
            thresholds.max_daily_trades_multiplier = 0.7
            self.logger.info("🐻 BEAR LOW VOL: Conservative thresholds")

        elif regime == MarketRegime.BULL_HIGH_LIQUIDITY:
            # BULL HIGH LIQUIDITY: Relajar para capturar momentum
            thresholds.vwap_price_tolerance_pct = 2.5  # Más permisivo
            thresholds.vwap_trend_tolerance_pct = -0.15  # Allow slight pullbacks
            thresholds.min_pattern_completion = 20.0  # Entrar más temprano
            thresholds.min_quality_score = 45.0  # Aceptar calidad media
            thresholds.min_volume_ratio = 0.8  # Volumen menos crítico
            thresholds.min_divergence_strength = 25.0  # Divergencias débiles OK
            thresholds.max_daily_trades_multiplier = 1.3  # Más trades
            self.logger.info("🐂 BULL HIGH LIQUIDITY: Relaxed thresholds")

        elif regime == MarketRegime.BULL_LOW_LIQUIDITY:
            # BULL LOW LIQUIDITY: Relajar moderadamente (ej: viernes tarde)
            thresholds.vwap_price_tolerance_pct = 3.0  # Muy permisivo
            thresholds.vwap_trend_tolerance_pct = -0.2  # Allow consolidation
            thresholds.min_pattern_completion = 25.0
            thresholds.min_quality_score = 40.0  # Friday relaxation
            thresholds.min_volume_ratio = 0.7  # Low volume OK
            thresholds.min_divergence_strength = 30.0
            thresholds.max_daily_trades_multiplier = 1.0
            self.logger.info("🐂 BULL LOW LIQUIDITY: Friday-style relaxation")

        elif regime == MarketRegime.CHOPPY:
            # CHOPPY: Selectivo pero no demasiado restrictivo
            # RELAXED: Aumentar tolerancias VWAP para capturar más oportunidades válidas
            # Problem: Era demasiado estricto (1.8%/-0.05%) y rechazaba 60% de oportunidades
            # Solution: Relajar a niveles similares a TRENDING pero mantener calidad alta
            thresholds.vwap_price_tolerance_pct = 2.3  # Was 1.8%, now 2.3% (similar a TRENDING 2.5%)
            thresholds.vwap_trend_tolerance_pct = -0.12  # Was -0.05%, now -0.12% (allow more pullbacks)
            thresholds.min_pattern_completion = 30.0
            thresholds.min_quality_score = 55.0
            thresholds.min_volume_ratio = 1.1
            thresholds.min_divergence_strength = 35.0
            thresholds.max_daily_trades_multiplier = 0.8
            self.logger.info("🌊 CHOPPY: Selective thresholds (VWAP relaxed to capture valid opportunities)")

        else:
            # UNKNOWN: Use baseline with slight caution
            thresholds.max_daily_trades_multiplier = 0.9
            self.logger.info("❓ UNKNOWN REGIME: Using baseline with caution")

        return thresholds

    def _apply_catalyst_override(
        self,
        base_thresholds: WorkerThresholds,
        conditions: MarketConditions,
        opportunity: Dict
    ) -> WorkerThresholds:
        """
        SMALLCAP-AWARE: Override regime thresholds based on individual ticker context

        Logic:
        - Strong catalyst (FDA, M&A, etc.) → Relax thresholds even in BEAR market
        - High volume (5x+) → Ignore SPY regime, focus on ticker momentum
        - High quality (85+) → Override conservative mode
        - Panic mode → Still NO override (protection first)

        Args:
            base_thresholds: Thresholds calculated from SPY regime
            conditions: Current market conditions
            opportunity: Ticker opportunity with catalyst_type, volume_ratio, quality_score

        Returns:
            Modified thresholds with catalyst override applied
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        catalyst_type = opportunity.get('catalyst_type', 'NONE')
        volume_ratio = opportunity.get('volume_ratio', 0.0)
        quality_score = opportunity.get('quality_score', 0.0)

        # Copy base thresholds (don't modify original)
        import copy
        thresholds = copy.deepcopy(base_thresholds)

        # === PANIC MODE: NO OVERRIDES (safety first) ===
        if conditions.regime == MarketRegime.PANIC:
            self.logger.debug(f"🚨 {symbol}: PANIC mode - no catalyst override")
            return thresholds

        # === CATALYST OVERRIDE ===
        strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT', 'NEWS']
        has_strong_catalyst = catalyst_type in strong_catalysts

        if has_strong_catalyst:
            # Strong catalyst → Override conservative regime
            override_level = "moderate"

            if volume_ratio >= 5.0:
                # Very strong: Catalyst + extreme volume
                override_level = "aggressive"
            elif volume_ratio >= 2.5:
                # Strong: Catalyst + high volume
                override_level = "strong"

            if override_level == "aggressive":
                # Treat like BULL_HIGH_LIQUIDITY regardless of SPY
                thresholds.vwap_price_tolerance_pct = 2.5
                thresholds.vwap_trend_tolerance_pct = -0.15
                thresholds.min_quality_score = 45.0
                thresholds.min_pattern_completion = 20.0
                thresholds.min_volume_ratio = 1.0
                self.logger.info(
                    f"🔥 {symbol}: CATALYST OVERRIDE (aggressive) - "
                    f"{catalyst_type} + {volume_ratio:.1f}x vol"
                )

            elif override_level == "strong":
                # Relax significantly
                thresholds.vwap_price_tolerance_pct = max(
                    thresholds.vwap_price_tolerance_pct, 2.0
                )
                thresholds.vwap_trend_tolerance_pct = max(
                    thresholds.vwap_trend_tolerance_pct, -0.10
                )
                thresholds.min_quality_score = max(
                    thresholds.min_quality_score - 15, 40.0
                )
                self.logger.info(
                    f"⚡ {symbol}: CATALYST OVERRIDE (strong) - "
                    f"{catalyst_type} + {volume_ratio:.1f}x vol"
                )

            else:  # moderate
                # Relax moderately
                thresholds.vwap_price_tolerance_pct = max(
                    thresholds.vwap_price_tolerance_pct, 1.8
                )
                thresholds.min_quality_score = max(
                    thresholds.min_quality_score - 10, 45.0
                )
                self.logger.info(
                    f"💡 {symbol}: CATALYST OVERRIDE (moderate) - {catalyst_type}"
                )

        # === VOLUME OVERRIDE (technical breakout without news) ===
        elif volume_ratio >= 8.0:
            # Extreme volume without catalyst → Probably something happening
            thresholds.vwap_price_tolerance_pct = 2.2
            thresholds.vwap_trend_tolerance_pct = -0.10
            thresholds.min_quality_score = max(thresholds.min_quality_score - 10, 45.0)
            self.logger.info(
                f"📊 {symbol}: VOLUME OVERRIDE - {volume_ratio:.1f}x extreme volume"
            )

        # === QUALITY OVERRIDE (high confidence setup) ===
        elif quality_score >= 85.0:
            # Very high quality → Trust the setup even in bear market
            thresholds.min_quality_score = max(thresholds.min_quality_score - 5, 50.0)
            thresholds.vwap_price_tolerance_pct = max(
                thresholds.vwap_price_tolerance_pct, 1.8
            )
            self.logger.info(
                f"⭐ {symbol}: QUALITY OVERRIDE - {quality_score:.0f} score"
            )

        return thresholds

    # === CONVENIENCE GETTERS (for easy worker integration) ===

    def get_vwap_price_tolerance(self) -> float:
        """Get current VWAP price tolerance %"""
        return self.get_thresholds().vwap_price_tolerance_pct

    def get_vwap_trend_tolerance(self) -> float:
        """Get current VWAP trend tolerance %"""
        return self.get_thresholds().vwap_trend_tolerance_pct

    def get_min_quality_score(self) -> float:
        """Get current minimum quality score"""
        return self.get_thresholds().min_quality_score

    def get_min_pattern_completion(self) -> float:
        """Get current minimum pattern completion %"""
        return self.get_thresholds().min_pattern_completion

    def get_min_volume_ratio(self) -> float:
        """Get current minimum volume ratio"""
        return self.get_thresholds().min_volume_ratio

    def get_position_size_multiplier(self) -> float:
        """Get position size adjustment multiplier"""
        return self.get_thresholds().position_size_multiplier

    def should_allow_entries(self) -> bool:
        """Check if entries should be allowed in current regime"""
        return self.get_thresholds().allow_entries

    def get_regime_summary(self) -> Dict:
        """Get human-readable summary of current regime and thresholds"""
        conditions = self.regime_detector.get_current_regime()
        thresholds = self.get_thresholds()

        if not conditions:
            return {"error": "No market conditions available"}

        return {
            "regime": conditions.regime.value,
            "confidence": f"{conditions.confidence:.0f}%",
            "spy_trend": f"{conditions.spy_trend:+.2f}%",
            "liquidity": f"{conditions.liquidity_score:.0f}/100",
            "entries_allowed": thresholds.allow_entries,
            "thresholds": {
                "vwap_tolerance": f"{thresholds.vwap_price_tolerance_pct:.1f}%",
                "min_quality": f"{thresholds.min_quality_score:.0f}",
                "position_size": f"{thresholds.position_size_multiplier:.1f}x",
                "max_trades": f"{thresholds.max_daily_trades_multiplier:.1f}x"
            }
        }


# Singleton accessor
_manager_instance = None

def get_adaptive_threshold_manager() -> AdaptiveThresholdManager:
    """Get singleton instance of adaptive threshold manager"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AdaptiveThresholdManager()
    return _manager_instance
