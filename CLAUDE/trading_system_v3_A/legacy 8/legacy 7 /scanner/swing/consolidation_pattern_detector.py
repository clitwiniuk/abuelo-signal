"""Consolidation Pattern Detector for Swing Trading

Detects 5 consolidation patterns:
1. ASCENDING_TRIANGLE (best bullish)
2. BULL_FLAG
3. CUP_AND_HANDLE
4. FLAT_BASE
5. DESCENDING_TRIANGLE (weakest)

Scoring system 0-100 based on:
- Pattern quality (25pts)
- Volume compression (20pts)
- Duration (20pts)
- Proximity to resistance (20pts)
- Touches (15pts)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import talib  # Assume available

class ConsolidationPatternDetector:
    def __init__(self):
        self.pattern_scores = {
            'ASCENDING_TRIANGLE': 25,
            'BULL_FLAG': 22,
            'CUP_AND_HANDLE': 23,
            'FLAT_BASE': 20,
            'DESCENDING_TRIANGLE': 15
        }

    def detect_pattern(self, df: pd.DataFrame) -> Dict:
        """
        Main detection method.
        df: daily OHLCV data, last 130 days
        Returns: pattern dict or None
        """
        if len(df) < 20:
            return None

        # Basic consolidation check
        consolidation = self._check_consolidation(df)
        if not consolidation:
            return None

        # Pattern specific detection
        patterns = []
        patterns.append(self._detect_ascending_triangle(df))
        patterns.append(self._detect_bull_flag(df))
        patterns.append(self._detect_cup_handle(df))
        patterns.append(self._detect_flat_base(df))
        patterns.append(self._detect_descending_triangle(df))

        # Best pattern
        best_pattern = max(patterns, key=lambda p: p.get('score', 0)) if patterns else None
        if best_pattern and best_pattern['score'] > 0:
            best_pattern.update(consolidation)
            best_pattern['breakout_score'] = self._calculate_breakout_score(best_pattern, df)
            best_pattern['entry_mode'] = self._determine_entry_mode(df)
            return best_pattern

        return None

    def _check_consolidation(self, df: pd.DataFrame) -> Dict:
        """Basic consolidation criteria"""
        highs = df['High'].tail(120)
        lows = df['Low'].tail(120)
        range_pct = (highs.max() - lows.min()) / ((highs + lows)/2).mean() * 100
        if range_pct > 50:  # Relaxed
            return None

        resistance = highs.quantile(0.9)
        support = lows.quantile(0.1)
        touches_res = sum(highs >= resistance * 0.99)
        touches_sup = sum(lows <= support * 1.01)

        if touches_res < 1 or touches_sup < 1:  # Relaxed
            return None

        days = len(df)
        return {
            'consolidation_days': days,
            'resistance': resistance,
            'support': support,
            'touches_resistance': touches_res,
            'touches_support': touches_sup,
            'range_pct': range_pct
        }

    def _detect_ascending_triangle(self, df: pd.DataFrame) -> Dict:
        """Ascending Triangle: higher lows, flat resistance"""
        highs = df['High'].rolling(10).max()
        lows = df['Low'].rolling(10).min()
        # Simple heuristic
        resistance_flat = highs.std() / highs.mean() < 0.02
        higher_lows = lows.diff().tail(20).mean() > 0
        score = 25 if resistance_flat and higher_lows else 0
        return {'pattern_type': 'ASCENDING_TRIANGLE', 'score': score}

    def _detect_bull_flag(self, df: pd.DataFrame) -> Dict:
        """Bull Flag: tight consolidation after uptrend"""
        prior_trend = (df['Close'].tail(30).iloc[-1] - df['Close'].tail(60).iloc[0]) / df['Close'].tail(60).iloc[0] > 0.1
        tight_range = (df['High'].tail(20).max() - df['Low'].tail(20).min()) / df['Close'].tail(20).mean() < 0.15
        score = 22 if prior_trend and tight_range else 0
        return {'pattern_type': 'BULL_FLAG', 'score': score}

    def _detect_cup_handle(self, df: pd.DataFrame) -> Dict:
        """Cup & Handle: U-shape + handle"""
        # Simplified
        mid_low = df['Low'].tail(60).min()
        cup_left = df['Close'][(df['Low'] - mid_low).abs() < 0.01].index[0]
        cup_right = df['Close'][(df['Low'] - mid_low).abs() < 0.01].index[-1]
        handle_tight = (df['High'].tail(20).max() - df['Low'].tail(20).min()) / df['Close'].tail(20).mean() < 0.1
        score = 23 if handle_tight else 0
        return {'pattern_type': 'CUP_AND_HANDLE', 'score': score}

    def _detect_flat_base(self, df: pd.DataFrame) -> Dict:
        """Flat Base: horizontal range"""
        highs_std = df['High'].tail(40).std() / df['High'].tail(40).mean()
        lows_std = df['Low'].tail(40).std() / df['Low'].tail(40).mean()
        flat = highs_std < 0.03 and lows_std < 0.03
        score = 20 if flat else 0
        return {'pattern_type': 'FLAT_BASE', 'score': score}

    def _detect_descending_triangle(self, df: pd.DataFrame) -> Dict:
        """Descending Triangle: lower highs, flat support"""
        highs = df['High'].rolling(10).max()
        lows = df['Low'].rolling(10).min()
        support_flat = lows.std() / lows.mean() < 0.02
        lower_highs = highs.diff().tail(20).mean() < 0
        score = 15 if support_flat and lower_highs else 0
        return {'pattern_type': 'DESCENDING_TRIANGLE', 'score': score}

    def _calculate_breakout_score(self, pattern: Dict, df: pd.DataFrame) -> float:
        """Composite score 0-100"""
        score = 0

        # Pattern quality
        score += pattern.get('score', 0)

        # Volume compression
        vol_mean = df['Volume'].tail(60).mean()
        vol_recent = df['Volume'].tail(10).mean()
        compression = vol_recent / vol_mean
        score += min(20, max(0, 20 * (1 - compression))) if compression < 1 else 0

        # Duration optimal
        days = pattern['consolidation_days']
        if 30 <= days <= 90:
            score += 20
        elif 20 <= days < 30 or 90 < days <= 120:
            score += 10
        else:
            score += 0

        # Proximity resistance
        current = df['Close'].iloc[-1]
        dist = (current - pattern['resistance']) / pattern['resistance'] * 100
        if dist <= 1:
            score += 20
        elif dist <= 3:
            score += 15
        elif dist <= 5:
            score += 10
        else:
            score += 0

        # Touches
        touches_r = pattern['touches_resistance']
        touches_s = pattern['touches_support']
        touches_score = min(15, (touches_r + touches_s) * 3)
        score += touches_score

        return min(100, score)

    def _determine_entry_mode(self, df: pd.DataFrame) -> str:
        """BREAKOUT or PULLBACK based on premarket gap"""
        # Simulate gap from previous close to current open
        prev_close = df['Close'].iloc[-2]
        current_open = df['Open'].iloc[-1]
        gap = (current_open - prev_close) / prev_close * 100
        if gap < 3:
            return 'BREAKOUT'
        elif gap > 5:
            return 'PULLBACK'
        return 'BREAKOUT'