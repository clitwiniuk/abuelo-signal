"""
Pattern Generator
=================

Generador de patrones sintéticos para testing de workers.
Crea datos realistas que simulan oportunidades del scanner en vivo.
"""

import random
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import pandas as pd


class PatternGenerator:
    """Generador de patrones sintéticos para testing de workers"""
    
    def __init__(self, seed: int = 42):
        """
        Inicializa el generador de patrones
        
        Args:
            seed: Seed para reproducibilidad
        """
        random.seed(seed)
        np.random.seed(seed)
        
        # Catalysts comunes del mercado
        self.catalysts = [
            'FDA', 'EARNINGS', 'GUIDANCE', 'M&A', 'ANALYST_UPGRADE',
            'ANALYST_DOWNGRADE', 'NEWS', 'PRODUCT_LAUNCH', 'PARTNERSHIP',
            'LEGAL', 'REGULATORY', 'ECONOMIC_DATA', 'CONFERENCE'
        ]
        
        # Símbolos para testing
        self.symbols = [f'TEST{i:03d}' for i in range(1, 51)]
        
        # Rangos de precios por categoría
        self.price_ranges = {
            'penny_stock': (0.50, 4.99),
            'small_cap': (5.00, 19.99),
            'mid_cap': (20.00, 99.99),
            'large_cap': (100.00, 500.00)
        }
        
        logger.info(f"🎯 PatternGenerator inicializado con seed {seed}")

    def generate_mixed_patterns(self, count: int) -> List[Dict[str, Any]]:
        """
        Genera una mezcla variada de patrones
        
        Args:
            count: Número de patrones a generar
            
        Returns:
            Lista de patrones sintéticos
        """
        patterns = []
        
        # Distribución de tipos de patrones
        pattern_distribution = {
            'gap_go': 0.20,
            'bull_flag': 0.15,
            'macdv': 0.20,
            'daily_plays': 0.25,
            'vwap_breakout': 0.15,
            'momentum_breakout': 0.05
        }
        
        remaining = count
        for pattern_type, ratio in pattern_distribution.items():
            num_patterns = int(count * ratio) if remaining > 0 else 0
            patterns.extend(self.generate_patterns_by_type(pattern_type, num_patterns))
            remaining -= num_patterns
        
        # Fill remaining with generic patterns
        while len(patterns) < count:
            patterns.append(self.generate_single_pattern('generic'))
        
        # Shuffle para mezclar tipos
        random.shuffle(patterns)
        
        return patterns[:count]

    def generate_patterns_by_type(self, pattern_type: str, count: int) -> List[Dict[str, Any]]:
        """Genera patrones específicos de un tipo"""
        if count <= 0:
            return []
        
        patterns = []
        
        for _ in range(count):
            pattern = self.generate_single_pattern(pattern_type)
            patterns.append(pattern)
        
        return patterns

    def generate_single_pattern(self, pattern_type: str = 'generic') -> Dict[str, Any]:
        """
        Genera un patrón sintético individual
        
        Args:
            pattern_type: Tipo de patrón ('gap_go', 'bull_flag', 'macdv', etc.)
            
        Returns:
            Dict con datos del patrón
        """
        # Datos básicos
        symbol = random.choice(self.symbols)
        current_price = self._generate_realistic_price()
        catalyst_type = random.choice(self.catalysts)
        
        # Generar según el tipo específico
        if pattern_type == 'gap_go':
            pattern = self._generate_gap_go_pattern(symbol, current_price, catalyst_type)
        elif pattern_type == 'bull_flag':
            pattern = self._generate_bull_flag_pattern(symbol, current_price, catalyst_type)
        elif pattern_type == 'macdv':
            pattern = self._generate_macdv_pattern(symbol, current_price, catalyst_type)
        elif pattern_type == 'daily_plays':
            pattern = self._generate_daily_plays_pattern(symbol, current_price, catalyst_type)
        elif pattern_type == 'vwap_breakout':
            pattern = self._generate_vwap_pattern(symbol, current_price, catalyst_type)
        elif pattern_type == 'momentum_breakout':
            pattern = self._generate_momentum_pattern(symbol, current_price, catalyst_type)
        else:
            pattern = self._generate_generic_pattern(symbol, current_price, catalyst_type)
        
        # Agregar datos comunes
        pattern.update({
            'symbol': symbol,
            'current_price': current_price,
            'catalyst_type': catalyst_type,
            'pattern_type': pattern_type,
            'timestamp': datetime.now().isoformat()
        })
        
        return pattern

    def _generate_realistic_price(self) -> float:
        """Genera precio realista con distribución ponderada"""
        categories = list(self.price_ranges.keys())
        weights = [0.30, 0.40, 0.25, 0.05]  # Penny stocks más comunes
        
        chosen_category = np.random.choice(categories, p=weights)
        min_price, max_price = self.price_ranges[chosen_category]
        
        # Log-normal distribution para precios más realistas
        log_price = np.random.normal(np.log(min_price + max_price) / 2, 0.5)
        price = np.exp(log_price)
        
        return max(min_price, min(max_price, price))

    def _generate_gap_go_pattern(self, symbol: str, price: float, catalyst: str) -> Dict[str, Any]:
        """Genera patrón Gap-Go (gap > 8%)"""
        gap_percentage = random.uniform(8.0, 25.0)
        volume_ratio = random.uniform(2.0, 8.0)
        quality_score = self._calculate_quality_score('gap_go', gap_percentage, volume_ratio, catalyst)
        
        # Simular barras intraday para Gap-Go
        bars = self._generate_intraday_bars(price, 'gap_go', bars_count=60)
        
        return {
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'quality_score': quality_score,
            'bars': bars,
            'expected_move': gap_percentage * 0.6,  # Gap-Go típicamente continúa
            'support_level': price * 0.98,
            'resistance_level': price * 1.05
        }

    def _generate_bull_flag_pattern(self, symbol: str, price: float, catalyst: str) -> Dict[str, Any]:
        """Genera patrón Bull Flag (gap moderado + consolidación)"""
        gap_percentage = random.uniform(3.0, 8.0)  # Gap moderado para flagpole
        volume_ratio = random.uniform(1.5, 4.0)
        quality_score = self._calculate_quality_score('bull_flag', gap_percentage, volume_ratio, catalyst)
        
        # Bull Flag necesita consolidación después del gap
        bars = self._generate_intraday_bars(price, 'bull_flag', bars_count=90)
        
        return {
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'quality_score': quality_score,
            'bars': bars,
            'expected_move': gap_percentage * 0.8,  # Flagpole projection
            'consolidation_detected': True,
            'flag_quality': quality_score / 100
        }

    def _generate_macdv_pattern(self, symbol: str, price: float, catalyst: str) -> Dict[str, Any]:
        """Genera patrón MACD Divergence"""
        gap_percentage = random.uniform(-2.0, 5.0)  # Gap más pequeño para MACD
        volume_ratio = random.uniform(1.2, 3.0)
        quality_score = self._calculate_quality_score('macdv', gap_percentage, volume_ratio, catalyst)
        
        # MACD patterns más técnicos
        bars = self._generate_intraday_bars(price, 'macdv', bars_count=120)
        
        return {
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'quality_score': quality_score,
            'bars': bars,
            'macd_divergence': True,
            'rsi_level': random.uniform(30, 70),
            'expected_reversal': True
        }

    def _generate_daily_plays_pattern(self, symbol: str, price: float, catalyst: str) -> Dict[str, Any]:
        """Genera patrón Daily Plays (catalyst-driven)"""
        # Daily plays pueden tener gaps variables
        gap_percentage = random.uniform(-5.0, 15.0)
        volume_ratio = random.uniform(1.5, 6.0)
        quality_score = self._calculate_quality_score('daily_plays', gap_percentage, volume_ratio, catalyst)
        
        # Bars para análisis diario
        bars = self._generate_intraday_bars(price, 'daily_plays', bars_count=150)
        
        return {
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'quality_score': quality_score,
            'bars': bars,
            'catalyst_strength': self._assess_catalyst_strength(catalyst),
            'news_sentiment': random.choice(['positive', 'neutral', 'negative']),
            'analyst_coverage': random.choice([True, False])
        }

    def _generate_vwap_pattern(self, symbol: str, price: float, catalyst: str) -> Dict[str, Any]:
        """Genera patrón VWAP Breakout"""
        gap_percentage = random.uniform(-1.0, 8.0)  # VWAP patterns suelen tener gaps menores
        volume_ratio = random.uniform(1.8, 5.0)
        quality_score = self._calculate_quality_score('vwap_breakout', gap_percentage, volume_ratio, catalyst)
        
        # VWAP necesita más barras para calcular promedio
        bars = self._generate_intraday_bars(price, 'vwap_breakout', bars_count=100)
        
        return {
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'quality_score': quality_score,
            'bars': bars,
            'vwap_distance': random.uniform(-2.0, 3.0),  # % distance from VWAP
            'vwap_trend': random.choice(['rising', 'flat', 'falling']),
            'volume_profile': 'bullish' if volume_ratio > 2.5 else 'mixed'
        }

    def _generate_momentum_pattern(self, symbol: str, price: float, catalyst: str) -> Dict[str, Any]:
        """Genera patrón Momentum Breakout"""
        gap_percentage = random.uniform(2.0, 12.0)
        volume_ratio = random.uniform(2.0, 7.0)
        quality_score = self._calculate_quality_score('momentum_breakout', gap_percentage, volume_ratio, catalyst)
        
        bars = self._generate_intraday_bars(price, 'momentum_breakout', bars_count=80)
        
        return {
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'quality_score': quality_score,
            'bars': bars,
            'momentum_strength': random.uniform(0.5, 1.0),
            'acceleration': random.choice(['increasing', 'steady', 'decreasing']),
            'breakout_level': price * 1.02
        }

    def _generate_generic_pattern(self, symbol: str, price: float, catalyst: str) -> Dict[str, Any]:
        """Genera patrón genérico (para casos no específicos)"""
        gap_percentage = random.uniform(-3.0, 10.0)
        volume_ratio = random.uniform(0.8, 3.0)
        quality_score = random.uniform(30, 70)
        
        bars = self._generate_intraday_bars(price, 'generic', bars_count=50)
        
        return {
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'quality_score': quality_score,
            'bars': bars,
            'generic_setup': True
        }

    def _calculate_quality_score(self, pattern_type: str, gap_pct: float, 
                               volume_ratio: float, catalyst: str) -> float:
        """
        Calcula quality score basado en criterios del patrón
        
        Args:
            pattern_type: Tipo de patrón
            gap_pct: Gap percentage
            volume_ratio: Ratio de volumen
            catalyst: Tipo de catalyst
            
        Returns:
            Quality score (0-100)
        """
        score = 50.0  # Base score
        
        # Gap scoring (depende del patrón)
        if pattern_type in ['gap_go', 'momentum_breakout']:
            # Prefiere gaps grandes
            if gap_pct > 10:
                score += 20
            elif gap_pct > 5:
                score += 10
        elif pattern_type == 'bull_flag':
            # Prefiere gaps moderados
            if 3 <= gap_pct <= 8:
                score += 20
            elif 2 <= gap_pct <= 12:
                score += 10
        elif pattern_type == 'macdv':
            # Gap pequeño es mejor para reversiones
            if -2 <= gap_pct <= 5:
                score += 15
        else:
            # Generic scoring
            if 2 <= gap_pct <= 15:
                score += 10
        
        # Volume scoring
        if volume_ratio > 4:
            score += 20
        elif volume_ratio > 2:
            score += 10
        elif volume_ratio > 1.5:
            score += 5
        elif volume_ratio < 0.5:
            score -= 15
        
        # Catalyst scoring
        catalyst_scores = {
            'FDA': 25, 'EARNINGS': 20, 'M&A': 25, 'ANALYST_UPGRADE': 15,
            'PRODUCT_LAUNCH': 20, 'PARTNERSHIP': 15, 'NEWS': 10,
            'GUIDANCE': 15, 'ANALYST_DOWNGRADE': -10, 'LEGAL': -20,
            'REGULATORY': -15, 'ECONOMIC_DATA': 5, 'CONFERENCE': 5
        }
        
        score += catalyst_scores.get(catalyst, 0)
        
        # Ensure score is in valid range
        return max(0, min(100, score))

    def _assess_catalyst_strength(self, catalyst: str) -> str:
        """Evalúa la fuerza del catalyst"""
        strong_catalysts = ['FDA', 'M&A', 'EARNINGS']
        medium_catalysts = ['GUIDANCE', 'PRODUCT_LAUNCH', 'ANALYST_UPGRADE']
        weak_catalysts = ['NEWS', 'CONFERENCE', 'ECONOMIC_DATA']
        
        if catalyst in strong_catalysts:
            return 'strong'
        elif catalyst in medium_catalysts:
            return 'medium'
        elif catalyst in weak_catalysts:
            return 'weak'
        else:
            return 'unknown'

    def _generate_intraday_bars(self, base_price: float, pattern_type: str, 
                              bars_count: int = 60) -> List[Dict[str, Any]]:
        """
        Genera barras intraday sintéticas
        
        Args:
            base_price: Precio base
            pattern_type: Tipo de patrón (afecta la forma de las barras)
            bars_count: Número de barras a generar
            
        Returns:
            Lista de barras OHLCV
        """
        bars = []
        current_price = base_price
        
        for i in range(bars_count):
            # Simular movimiento del precio según patrón
            if pattern_type == 'gap_go':
                # Gap-Go: movimiento alcista continuo
                price_change = random.uniform(-0.02, 0.04) * current_price
            elif pattern_type == 'bull_flag':
                # Bull Flag: subida, luego consolidación
                if i < bars_count * 0.3:  # Pole
                    price_change = random.uniform(0.01, 0.05) * current_price
                else:  # Flag
                    price_change = random.uniform(-0.02, 0.02) * current_price
            elif pattern_type == 'macdv':
                # MACD: movimientos más pequeños, reversiones
                price_change = random.uniform(-0.015, 0.015) * current_price
            elif pattern_type == 'daily_plays':
                # Daily Plays: movimiento dirigido por catalyst
                price_change = random.uniform(0, 0.03) * current_price
            elif pattern_type == 'vwap_breakout':
                # VWAP: test de VWAP y breakout
                if i < bars_count * 0.7:
                    price_change = random.uniform(-0.01, 0.01) * current_price
                else:
                    price_change = random.uniform(0.01, 0.03) * current_price
            else:  # generic
                price_change = random.uniform(-0.02, 0.02) * current_price
            
            # Evitar precios negativos
            new_price = max(0.01, current_price + price_change)
            
            # Generar OHLC
            high = new_price * random.uniform(1.0, 1.015)
            low = new_price * random.uniform(0.985, 1.0)
            open_price = random.uniform(low, high)
            close_price = new_price
            
            # Volume simulado
            base_volume = 100000
            volume_multiplier = random.uniform(0.5, 3.0)
            volume = int(base_volume * volume_multiplier)
            
            # Timestamp (cada barra = 1 minuto)
            timestamp = datetime.now() - timedelta(minutes=bars_count - i)
            
            bar = {
                'timestamp': timestamp.isoformat(),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close_price, 2),
                'volume': volume
            }
            
            bars.append(bar)
            current_price = new_price
        
        return bars

    def get_pattern_summary(self, patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Genera resumen estadístico de patrones generados
        
        Args:
            patterns: Lista de patrones
            
        Returns:
            Dict con estadísticas
        """
        if not patterns:
            return {}
        
        # Análisis por tipo
        type_counts = {}
        quality_scores = []
        gap_percentages = []
        volume_ratios = []
        
        for pattern in patterns:
            pattern_type = pattern.get('pattern_type', 'unknown')
            type_counts[pattern_type] = type_counts.get(pattern_type, 0) + 1
            
            quality_scores.append(pattern.get('quality_score', 0))
            gap_percentages.append(pattern.get('gap_percentage', 0))
            volume_ratios.append(pattern.get('volume_ratio', 0))
        
        summary = {
            'total_patterns': len(patterns),
            'pattern_types': type_counts,
            'quality_stats': {
                'mean': np.mean(quality_scores),
                'std': np.std(quality_scores),
                'min': np.min(quality_scores),
                'max': np.max(quality_scores)
            },
            'gap_stats': {
                'mean': np.mean(gap_percentages),
                'std': np.std(gap_percentages),
                'min': np.min(gap_percentages),
                'max': np.max(gap_percentages)
            },
            'volume_stats': {
                'mean': np.mean(volume_ratios),
                'std': np.std(volume_ratios),
                'min': np.min(volume_ratios),
                'max': np.max(volume_ratios)
            }
        }
        
        return summary


# Setup logging
import logging
logger = logging.getLogger(__name__)