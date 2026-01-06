"""
Realistic Workers for Backtesting
=================================

Workers simplificados que mantienen la lógica real de decisión
pero con parámetros realistas para backtesting.

Cada worker implementa criterios basados en los workers reales
pero sin dependencias complejas.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import random
import numpy as np

logger = logging.getLogger(__name__)


class BaseRealisticWorker(ABC):
    """Base class para workers realistas"""
    
    def __init__(self, worker_name: str, config: Dict[str, Any] = None):
        self.worker_name = worker_name
        self.config = config or {}
        self.logger = logger  # Add logger reference
        
        # Parámetros realistas basados en datos de mercado
        self.realistic_params = self._get_realistic_parameters()
        
        logger.info(f"🎯 {worker_name} initialized with realistic parameters")
    
    @abstractmethod
    def _get_realistic_parameters(self) -> Dict[str, Any]:
        """Retorna parámetros realistas específicos del worker"""
        pass
    
    @abstractmethod
    def evaluate_opportunity(self, opportunity: Dict[str, Any]) -> Tuple[bool, str, float]:
        """
        Evalúa oportunidad con lógica real
        
        Returns:
            Tuple[bool, str, float]: (should_enter, reason, confidence)
        """
        pass
    
    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Método asíncrono que WorkerTester espera
        
        Returns:
            bool: True si debe entrar, False si debe rechazar
        """
        try:
            should_enter, reason, confidence = self.evaluate_opportunity(opportunity)
            self.logger.debug(f"{self.worker_name} decision: {should_enter} - {reason} (confidence: {confidence:.1f})")
            return should_enter
        except Exception as e:
            self.logger.error(f"Error in should_enter for {self.worker_name}: {e}")
            return False
    
    async def should_exit(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Método de salida que WorkerTester puede usar
        """
        # Para backtesting, generalmente salimos rápido
        return True, "backtest_exit"
    
    def simulate_realistic_trade_result(self, opportunity: Dict[str, Any], 
                                      entry_price: float) -> Dict[str, Any]:
        """
        Simula resultado de trade con parámetros realistas
        """
        # Usar distribución realista basada en win rate real del worker
        win_rate = self.realistic_params['base_win_rate']
        avg_win = self.realistic_params['avg_win']
        avg_loss = self.realistic_params['avg_loss']
        
        # Determinar si es ganador
        is_win = random.random() < win_rate
        
        # Calcular PnL con variabilidad realista
        if is_win:
            # Winner: normal distribution around avg_win with realistic volatility
            volatility = avg_win * 0.4  # 40% volatility
            pnl = random.normalvariate(avg_win, volatility)
            # Cap extreme winners (realistic)
            pnl = min(pnl, avg_win * 3.0)
        else:
            # Loser: normal distribution around avg_loss with realistic volatility  
            volatility = abs(avg_loss) * 0.6  # 60% volatility for losers
            pnl = random.normalvariate(avg_loss, volatility)
            # Cap extreme losers
            pnl = max(pnl, avg_loss * 2.0)
        
        # Realistic hold time (15 min to 4 hours)
        hold_time = random.uniform(15, 240)
        
        # Realistic exit reasons
        if is_win:
            exit_reasons = ['profit_target', 'partial_profit', 'time_exit']
            weights = [0.7, 0.2, 0.1]  # Mostly profit targets
        else:
            exit_reasons = ['stop_loss', 'time_exit', 'pattern_break']
            weights = [0.8, 0.15, 0.05]  # Mostly stop losses
            
        exit_reason = random.choices(exit_reasons, weights=weights)[0]
        
        return {
            'pnl': pnl,
            'hold_time': hold_time,
            'exit_reason': exit_reason,
            'is_win': is_win,
            'entry_price': entry_price,
            'expected_win_rate': win_rate,
            'expected_avg_return': avg_win if is_win else avg_loss
        }


class MacdvRealisticWorker(BaseRealisticWorker):
    """
    Worker MACDV realista basado en la lógica del worker real
    
    Criterios reales del MACDV:
    - Gap 0-5% (no gaps parabólicos)
    - Volume ratio >= 0.7x (relajado)
    - Precio $1-$15 (smallcaps)
    - MACD divergence detection
    - Early entry strategy
    """
    
    def _get_realistic_parameters(self) -> Dict[str, Any]:
        return {
            'base_win_rate': 0.58,          # 58% win rate (realistic)
            'avg_win': 0.12,               # 12% average win
            'avg_loss': -0.06,             # 6% average loss
            'profit_factor_target': 1.4,   # Target profit factor
            'max_gap': 5.0,                # Max gap 5%
            'min_volume_ratio': 0.7,       # Min volume ratio
            'price_range': (1.0, 15.0),    # Smallcap range
            'quality_threshold': 50.0,     # Min quality score
            'macd_sensitivity': 0.7        # How sensitive to MACD signals
        }
    
    def evaluate_opportunity(self, opportunity: Dict[str, Any]) -> Tuple[bool, str, float]:
        """
        Evalúa oportunidad usando criterios MACDV reales
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        volume_ratio = opportunity.get('volume_ratio', 0)
        current_price = opportunity.get('current_price', 0)
        quality_score = opportunity.get('quality_score', 0)
        catalyst_type = opportunity.get('catalyst_type', 'NONE')
        
        try:
            # Criterio 1: Price range (smallcaps)
            if not (self.realistic_params['price_range'][0] <= current_price <= self.realistic_params['price_range'][1]):
                return False, f"Price ${current_price:.2f} outside smallcap range ${self.realistic_params['price_range'][0]}-${self.realistic_params['price_range'][1]}", 0.0
            
            # Criterio 2: Gap validation (avoid parabolic moves)
            if gap_pct > self.realistic_params['max_gap']:
                return False, f"Gap {gap_pct:.1f}% too large (max {self.realistic_params['max_gap']}%)", 0.0
            
            # Criterio 3: Volume requirement
            if volume_ratio < self.realistic_params['min_volume_ratio']:
                return False, f"Volume ratio {volume_ratio:.1f}x below minimum {self.realistic_params['min_volume_ratio']}x", 0.0
            
            # Criterio 4: Quality threshold
            if quality_score < self.realistic_params['quality_threshold']:
                return False, f"Quality score {quality_score:.1f} below threshold {self.realistic_params['quality_threshold']}", 0.0
            
            # Criterio 5: MACD divergence simulation (based on bars and pattern)
            bars = opportunity.get('bars', [])
            macd_score, macd_reason = self._simulate_macd_analysis(bars, current_price)
            
            if macd_score < 40:  # Minimum MACD score
                return False, f"Weak MACD signal ({macd_score:.0f}/100): {macd_reason}", 0.0
            
            # Criterio 6: Catalyst awareness (avoid major news unless high quality)
            major_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH']
            if catalyst_type in major_catalysts and quality_score < 75:
                return False, f"Major catalyst requires higher quality (have {quality_score:.1f}, need 75+)", 0.0
            
            # Calculate confidence based on criteria met
            confidence = self._calculate_macdv_confidence(opportunity, macd_score)
            
            # Additional checks for early entry strategy
            if self._is_too_late_for_entry(opportunity):
                return False, "Pattern too complete for early entry", confidence
            
            reason = (f"MACDV APPROVED - Gap {gap_pct:.1f}%, Volume {volume_ratio:.1f}x, "
                     f"Quality {quality_score:.1f}, MACD {macd_score:.0f}/100")
            
            return True, reason, confidence
            
        except Exception as e:
            logger.error(f"❌ Error evaluating MACDV opportunity: {e}")
            return False, f"Evaluation error: {str(e)}", 0.0
    
    def _simulate_macd_analysis(self, bars: List[Dict], current_price: float) -> Tuple[float, str]:
        """
        Simula análisis MACD basado en barras disponibles
        """
        if not bars or len(bars) < 35:
            return 60.0, "Insufficient bars, using default MACD score"
        
        # Simulate MACD calculation on available bars
        try:
            # Extract closing prices
            closes = [bar.get('close', 0) for bar in bars if 'close' in bar]
            
            if len(closes) < 35:
                return 60.0, "Insufficient price data"
            
            # Simple MACD simulation (12-period EMA - 26-period EMA)
            ema12 = self._calculate_ema(closes[-35:], 12)
            ema26 = self._calculate_ema(closes[-35:], 26)
            
            if ema12 is None or ema26 is None:
                return 60.0, "EMA calculation failed"
            
            macd_line = ema12 - ema26
            signal_line = macd_line * 0.9  # Simplified signal line
            
            # Calculate histogram
            histogram = macd_line - signal_line
            
            # Score based on MACD position and trend
            score = 50.0  # Base score
            
            # Bullish crossover or close to bullish
            if macd_line > signal_line:
                score += 25.0  # Above signal line
                if histogram > 0:
                    score += 15.0  # Positive momentum
            else:
                # Below signal line but narrowing
                if histogram > -0.02:  # Close to crossover
                    score += 10.0
            
            # Price vs MACD divergence check (simplified)
            recent_price_trend = (closes[-1] - closes[-10]) / closes[-10] if len(closes) >= 10 else 0
            macd_trend = (macd_line - (closes[-10] - self._calculate_ema(closes[-10:], 26))) / abs(macd_line) if len(closes) >= 10 else 0
            
            # Regular bullish divergence (price making lower lows, MACD higher lows)
            if recent_price_trend < -0.02 and macd_trend > 0.1:
                score += 20.0  # Divergence bonus
            
            # Final score with realistic limits
            score = max(0, min(100, score))
            
            reason = f"MACD {macd_line:.3f}, Signal {signal_line:.3f}, Hist {histogram:.3f}"
            return score, reason
            
        except Exception as e:
            logger.debug(f"Error in MACD simulation: {e}")
            return 60.0, f"MACD simulation error: {str(e)}"
    
    def _calculate_macdv_confidence(self, opportunity: Dict[str, Any], macd_score: float) -> float:
        """Calcula confidence score para MACDV"""
        confidence = 50.0  # Base
        
        # Add based on MACD strength
        confidence += (macd_score - 50) * 0.5
        
        # Quality score bonus
        quality = opportunity.get('quality_score', 0)
        if quality > 70:
            confidence += 15.0
        elif quality > 60:
            confidence += 10.0
        
        # Volume bonus
        volume_ratio = opportunity.get('volume_ratio', 0)
        if volume_ratio > 2.0:
            confidence += 10.0
        elif volume_ratio > 1.5:
            confidence += 5.0
        
        # Gap penalty (large gaps are risky for MACDV)
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        if gap_pct > 3.0:
            confidence -= 5.0
        
        return max(0, min(100, confidence))
    
    def _is_too_late_for_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Check if pattern is too complete for early entry"""
        # For MACDV, check if momentum is too strong (late entry)
        bars = opportunity.get('bars', [])
        if not bars or len(bars) < 10:
            return False
        
        # Simulate recent price momentum
        closes = [bar.get('close', 0) for bar in bars[-10:] if 'close' in bar]
        if len(closes) < 5:
            return False
        
        # Calculate recent momentum
        momentum = (closes[-1] - closes[-5]) / closes[-5]
        
        # Too much momentum suggests late entry
        return momentum > 0.08  # 8% gain in last 5 bars = too late
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate EMA (simplified)"""
        if len(prices) < period:
            return None
        
        try:
            multiplier = 2.0 / (period + 1)
            ema = sum(prices[:period]) / period  # Start with SMA
            
            for price in prices[period:]:
                ema = (price - ema) * multiplier + ema
            
            return ema
        except Exception:
            return None


class DailyPlaysRealisticWorker(BaseRealisticWorker):
    """
    Worker Daily Plays realista
    
    Enfoque: Catalyst-driven plays con calidad
    Win Rate: ~65%, Returns: más variables debido a catalysts
    """
    
    def _get_realistic_parameters(self) -> Dict[str, Any]:
        return {
            'base_win_rate': 0.65,          # 65% win rate
            'avg_win': 0.18,               # 18% average win (more variable)
            'avg_loss': -0.08,             # 8% average loss
            'profit_factor_target': 1.8,   # Higher due to catalyst plays
            'quality_threshold': 55.0,     # Slightly lower threshold
            'catalyst_bonus': 0.15,        # Catalyst plays get quality bonus
            'volume_requirement': 1.0,     # Basic volume requirement
            'gap_tolerance': 0.25          # More tolerant of gaps
        }
    
    def evaluate_opportunity(self, opportunity: Dict[str, Any]) -> Tuple[bool, str, float]:
        """Evalúa oportunidad con enfoque catalyst-driven"""
        symbol = opportunity.get('symbol', 'UNKNOWN')
        catalyst_type = opportunity.get('catalyst_type', 'NONE')
        quality_score = opportunity.get('quality_score', 0)
        volume_ratio = opportunity.get('volume_ratio', 0)
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        
        try:
            # Criterio 1: Catalyst check (core of daily plays)
            catalyst_scores = {
                'FDA': 90, 'M&A': 85, 'EARNINGS': 80, 'GUIDANCE': 70,
                'ANALYST_UPGRADE': 75, 'PRODUCT_LAUNCH': 75, 'NEWS': 60,
                'ANALYST_DOWNGRADE': 30, 'LEGAL': 20, 'REGULATORY': 25
            }
            
            catalyst_strength = catalyst_scores.get(catalyst_type, 40)
            
            # Criterio 2: Quality threshold
            adjusted_quality = quality_score + (catalyst_strength - 50) * 0.3  # Catalyst adjusts quality
            
            if adjusted_quality < self.realistic_params['quality_threshold']:
                return False, f"Adjusted quality {adjusted_quality:.1f} below threshold", 0.0
            
            # Criterio 3: Volume requirement (baseline)
            if volume_ratio < self.realistic_params['volume_requirement']:
                return False, f"Volume {volume_ratio:.1f}x below requirement", 0.0
            
            # Criterio 4: Gap tolerance (daily plays can handle larger gaps)
            if gap_pct > 20.0:  # Very generous gap tolerance
                return False, f"Gap {gap_pct:.1f}% too large", 0.0
            
            # Calculate confidence
            confidence = min(95.0, adjusted_quality * 0.8 + catalyst_strength * 0.2)
            
            reason = (f"Daily Plays APPROVED - Catalyst {catalyst_type} ({catalyst_strength}), "
                     f"Quality {quality_score:.1f}->{adjusted_quality:.1f}, Volume {volume_ratio:.1f}x")
            
            return True, reason, confidence
            
        except Exception as e:
            return False, f"Daily Plays evaluation error: {str(e)}", 0.0
    
    def simulate_realistic_trade_result(self, opportunity: Dict[str, Any], entry_price: float) -> Dict[str, Any]:
        """Simulate with higher volatility for catalyst plays"""
        result = super().simulate_realistic_trade_result(opportunity, entry_price)
        
        # Daily plays have higher volatility
        catalyst_type = opportunity.get('catalyst_type', 'NONE')
        
        # Adjust volatility based on catalyst strength
        catalyst_multiplier = {
            'FDA': 1.5, 'M&A': 1.4, 'EARNINGS': 1.3, 'GUIDANCE': 1.2,
            'ANALYST_UPGRADE': 1.2, 'PRODUCT_LAUNCH': 1.3, 'NEWS': 1.1
        }.get(catalyst_type, 1.0)
        
        # Increase volatility for high-catalyst plays
        if result['is_win']:
            result['pnl'] *= catalyst_multiplier
        else:
            result['pnl'] *= catalyst_multiplier
        
        return result


class VWAPRealisticWorker(BaseRealisticWorker):
    """
    Worker VWAP realista
    
    Enfoque: VWAP breakout strategy
    Win Rate: ~62%, conservador y consistente
    """
    
    def _get_realistic_parameters(self) -> Dict[str, Any]:
        return {
            'base_win_rate': 0.62,          # 62% win rate
            'avg_win': 0.09,               # 9% average win (conservative)
            'avg_loss': -0.05,             # 5% average loss
            'profit_factor_target': 1.3,   # Conservative target
            'vwap_distance_threshold': 2.0, # Max 2% from VWAP
            'volume_requirement': 1.5,     # Higher volume requirement
            'quality_threshold': 60.0,     # Higher quality requirement
            'consolidation_bonus': 0.1     # Bonus for consolidating stocks
        }
    
    def evaluate_opportunity(self, opportunity: Dict[str, Any]) -> Tuple[bool, str, float]:
        """Evalúa oportunidad con enfoque VWAP"""
        symbol = opportunity.get('symbol', 'UNKNOWN')
        quality_score = opportunity.get('quality_score', 0)
        volume_ratio = opportunity.get('volume_ratio', 0)
        
        try:
            # Criterio 1: Quality threshold (VWAP requires quality)
            if quality_score < self.realistic_params['quality_threshold']:
                return False, f"Quality {quality_score:.1f} below VWAP threshold", 0.0
            
            # Criterio 2: Volume requirement (VWAP needs institutional participation)
            if volume_ratio < self.realistic_params['volume_requirement']:
                return False, f"Volume {volume_ratio:.1f}x below VWAP requirement", 0.0
            
            # Criterio 3: Simulate VWAP analysis
            bars = opportunity.get('bars', [])
            vwap_score, vwap_reason = self._simulate_vwap_analysis(bars, opportunity)
            
            if vwap_score < 60:
                return False, f"Weak VWAP signal ({vwap_score:.0f}/100): {vwap_reason}", 0.0
            
            # Criterio 4: Check for consolidation (VWAP breakout preference)
            consolidation_score = self._check_consolidation(bars)
            
            confidence = vwap_score * 0.7 + consolidation_score * 0.3
            
            reason = f"VWAP APPROVED - Score {vwap_score:.0f}/100, Consolidation {consolidation_score:.0f}%, Reason: {vwap_reason}"
            
            return True, reason, confidence
            
        except Exception as e:
            return False, f"VWAP evaluation error: {str(e)}", 0.0
    
    def _simulate_vwap_analysis(self, bars: List[Dict], opportunity: Dict[str, Any]) -> Tuple[float, str]:
        """Simula análisis VWAP"""
        if not bars or len(bars) < 30:
            return 70.0, "Insufficient bars, using default"
        
        try:
            # Calculate simple VWAP from bars
            total_volume_price = sum((bar['high'] + bar['low'] + bar['close']) / 3 * bar['volume'] 
                                   for bar in bars if all(k in bar for k in ['high', 'low', 'close', 'volume']))
            total_volume = sum(bar['volume'] for bar in bars if 'volume' in bar)
            
            if total_volume == 0:
                return 60.0, "No volume data"
            
            vwap = total_volume_price / total_volume
            current_price = opportunity.get('current_price', 0)
            
            # Check distance from VWAP
            vwap_distance_pct = abs((current_price - vwap) / vwap) * 100
            
            # Score based on VWAP proximity
            if vwap_distance_pct <= 1.0:
                score = 90.0  # Excellent
                reason = f"Excellent VWAP proximity: {vwap_distance_pct:.2f}%"
            elif vwap_distance_pct <= 2.0:
                score = 75.0  # Good
                reason = f"Good VWAP proximity: {vwap_distance_pct:.2f}%"
            elif vwap_distance_pct <= 3.0:
                score = 60.0  # Acceptable
                reason = f"Acceptable VWAP proximity: {vwap_distance_pct:.2f}%"
            else:
                score = 40.0  # Poor
                reason = f"Poor VWAP proximity: {vwap_distance_pct:.2f}%"
            
            # Volume momentum check
            recent_volume = sum(bar['volume'] for bar in bars[-10:] if 'volume' in bar)
            earlier_volume = sum(bar['volume'] for bar in bars[-20:-10] if 'volume' in bar)
            
            if earlier_volume > 0:
                volume_momentum = recent_volume / earlier_volume
                if volume_momentum > 1.2:
                    score += 10.0  # Volume building
                    reason += f", Volume building {volume_momentum:.1f}x"
                elif volume_momentum < 0.8:
                    score -= 5.0   # Volume declining
                    reason += f", Volume declining {volume_momentum:.1f}x"
            
            return max(0, min(100, score)), reason
            
        except Exception as e:
            return 60.0, f"VWAP calculation error: {str(e)}"
    
    def _check_consolidation(self, bars: List[Dict]) -> float:
        """Check if stock is consolidating (good for VWAP breakout)"""
        if len(bars) < 20:
            return 50.0
        
        try:
            recent_highs = [bar['high'] for bar in bars[-20:] if 'high' in bar]
            recent_lows = [bar['low'] for bar in bars[-20:] if 'low' in bar]
            
            if not recent_highs or not recent_lows:
                return 50.0
            
            price_range = (max(recent_highs) - min(recent_lows)) / np.mean(recent_highs + recent_lows) * 100
            
            # Lower range = more consolidation
            if price_range < 2.0:
                return 90.0  # Excellent consolidation
            elif price_range < 4.0:
                return 75.0  # Good consolidation
            elif price_range < 6.0:
                return 60.0  # Acceptable consolidation
            else:
                return 30.0  # Poor consolidation
                
        except Exception:
            return 50.0


# Factory function to get realistic worker CLASSES (not instances)
def get_realistic_worker_class(worker_name: str) -> type:
    """
    Obtener CLASE de worker realista por nombre
    
    Returns:
        type: Clase del worker para que WorkerTester pueda instanciarla
    """
    
    workers = {
        'macdv': MacdvRealisticWorker,
        'daily_plays': DailyPlaysRealisticWorker,
        'vwap': VWAPRealisticWorker,
        'momentum_breakout': MomentumBreakoutRealisticWorker,
        'bull_flag': BullFlagRealisticWorker,
        'gap_go': GapGoRealisticWorker,
        
        # Mapeo de nombres compatibles con el sistema existente
        'momentum_breakout_worker_logic': MomentumBreakoutRealisticWorker,
        'vcp_smallcap': MomentumBreakoutRealisticWorker,  # Usar momentum para VCP smallcap
        'volume_absorption': GapGoRealisticWorker,  # Usar gap-go para volume absorption
        'generic_01': GapGoRealisticWorker  # Usar gap-go como worker genérico
    }
    
    worker_class = workers.get(worker_name.lower())
    if not worker_class:
        # Si no encuentra el worker específico, usar el genérico
        logger.warning(f"⚠️ Worker '{worker_name}' no encontrado, usando GapGoRealisticWorker como fallback")
        return GapGoRealisticWorker
    
    return worker_class


# Legacy function for backward compatibility (deprecated)
def get_realistic_worker(worker_name: str) -> BaseRealisticWorker:
    """Factory function to create realistic worker INSTANCES (deprecated)"""
    
    worker_class = get_realistic_worker_class(worker_name)
    return worker_class(worker_name)


# Additional worker implementations can be added here
class MomentumBreakoutRealisticWorker(BaseRealisticWorker):
    def _get_realistic_parameters(self):
        return {
            'base_win_rate': 0.55,
            'avg_win': 0.15,
            'avg_loss': -0.08,
            'profit_factor_target': 1.2
        }
    
    def evaluate_opportunity(self, opportunity):
        # Simplified momentum logic
        volume_ratio = opportunity.get('volume_ratio', 0)
        if volume_ratio > 2.0:
            return True, "Momentum APPROVED - High volume breakout", 75.0
        return False, "Momentum REJECTED - Insufficient volume", 0.0


class BullFlagRealisticWorker(BaseRealisticWorker):
    def _get_realistic_parameters(self):
        return {
            'base_win_rate': 0.60,
            'avg_win': 0.14,
            'avg_loss': -0.07,
            'profit_factor_target': 1.4
        }
    
    def evaluate_opportunity(self, opportunity):
        # Simplified bull flag logic
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        if 3.0 <= gap_pct <= 8.0:
            return True, "Bull Flag APPROVED - Proper gap range", 80.0
        return False, "Bull Flag REJECTED - Gap outside range", 0.0


class GapGoRealisticWorker(BaseRealisticWorker):
    def _get_realistic_parameters(self):
        return {
            'base_win_rate': 0.58,
            'avg_win': 0.12,
            'avg_loss': -0.06,
            'profit_factor_target': 1.3
        }
    
    def evaluate_opportunity(self, opportunity):
        # Simplified gap-go logic
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        volume_ratio = opportunity.get('volume_ratio', 0)
        if gap_pct > 8.0 and volume_ratio > 2.0:
            return True, "Gap Go APPROVED - Large gap with volume", 85.0
        return False, "Gap Go REJECTED - Insufficient gap or volume", 0.0