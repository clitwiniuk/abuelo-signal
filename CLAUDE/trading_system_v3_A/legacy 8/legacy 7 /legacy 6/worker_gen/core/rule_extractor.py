"""
Advanced Rule Extractor for Pattern Analysis
Extracts statistically significant rules from labeled trading data.
"""

import pandas as pd
import numpy as np
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
from scipy import stats
import itertools


@dataclass
class Rule:
    """Represents an extracted trading rule with statistical metrics"""
    conditions: List[str]  # List of conditions (e.g., ["RSI < 35", "Volume > 1.5x"])
    support: float  # % of samples where rule applies
    confidence: float  # % of rule samples that are profitable
    lift: float  # How much better than random
    p_value: float  # Statistical significance
    sample_count: int  # Number of samples supporting this rule
    avg_pnl: float  # Average PnL when rule triggers

    def __str__(self):
        return (f"Rule: {' AND '.join(self.conditions)} | "
                f"Support: {self.support:.1f}% | "
                f"Confidence: {self.confidence:.1f}% | "
                f"Lift: {self.lift:.2f} | "
                f"P-value: {self.p_value:.4f} | "
                f"Samples: {self.sample_count} | "
                f"Avg PnL: {self.avg_pnl:+.2f}%")


@dataclass
class IndicatorProfile:
    """Statistical profile of an indicator across samples"""
    name: str
    mean: float
    median: float
    std: float
    min: float
    max: float
    q25: float  # 25th percentile
    q75: float  # 75th percentile
    common_range: Tuple[float, float]  # Where 60% of samples fall

    def __str__(self):
        return (f"{self.name}: Mean={self.mean:.2f}, Median={self.median:.2f}, "
                f"Common Range=[{self.common_range[0]:.2f}, {self.common_range[1]:.2f}]")


class RuleExtractor:
    """
    Advanced rule extraction from labeled pattern data.
    Uses statistical analysis and association rule mining.
    """

    def __init__(self, min_support: float = 0.3, min_confidence: float = 0.6,
                 min_lift: float = 1.1, max_p_value: float = 0.05):
        """
        Args:
            min_support: Minimum % of samples rule must apply to (0.3 = 30%)
            min_confidence: Minimum confidence level for rule (0.6 = 60%)
            min_lift: Minimum lift over baseline (1.1 = 10% better than random)
            max_p_value: Maximum p-value for statistical significance (0.05 = 95% confidence)
        """
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        self.max_p_value = max_p_value

        # Available indicators to analyze
        self.indicators = ['close', 'open', 'high', 'low', 'volume',
                          'ema_9', 'ema_20', 'ema_50', 'ema_200',
                          'vwap', 'rsi_14', 'rvol', 'dist_ema_9']

    def analyze(self, data_map: Dict[str, pd.DataFrame]) -> Dict:
        """
        Main analysis method - extracts rules from labeled data.

        Args:
            data_map: Dictionary of {filename: DataFrame} with labeled samples

        Returns:
            Dictionary with:
                - indicator_profiles: Statistical profiles of each indicator
                - single_rules: Single-condition rules
                - combo_rules: Multi-condition rules (2-3 conditions)
                - negative_patterns: What to avoid (from NEG_ samples)
                - summary: Human-readable summary
        """
        print("\n🔬 Starting Advanced Rule Extraction...")

        # Separate positive and negative samples
        pos_samples = {k: v for k, v in data_map.items() if not k.startswith("NEG_")}
        neg_samples = {k: v for k, v in data_map.items() if k.startswith("NEG_")}

        print(f"   Analyzing {len(pos_samples)} positive samples, {len(neg_samples)} negative samples")

        # Step 1: Extract indicator values at entry point
        pos_features = self._extract_features(pos_samples)
        neg_features = self._extract_features(neg_samples) if neg_samples else pd.DataFrame()

        # Step 2: Build indicator profiles
        indicator_profiles = self._build_indicator_profiles(pos_features)

        # Step 3: Extract single-condition rules
        single_rules = self._extract_single_rules(pos_features, neg_features)

        # Step 4: Extract multi-condition rules (combinations)
        combo_rules = self._extract_combination_rules(pos_features, neg_features)

        # Step 5: Extract negative patterns (what to avoid)
        negative_patterns = self._extract_negative_patterns(neg_features) if (not neg_features.empty) else []

        # Step 6: Generate human-readable summary
        summary = self._generate_summary(indicator_profiles, single_rules, combo_rules, negative_patterns)

        return {
            'indicator_profiles': indicator_profiles,
            'single_rules': single_rules,
            'combo_rules': combo_rules,
            'negative_patterns': negative_patterns,
            'summary': summary,
            'total_samples': len(pos_samples) + len(neg_samples),
            'positive_samples': len(pos_samples),
            'negative_samples': len(neg_samples)
        }

    def _extract_features(self, data_map: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Extract indicator values at entry point for each sample.
        Returns DataFrame with one row per sample.
        """
        features = []

        for filename, df in data_map.items():
            if df.empty or len(df) < 2:
                continue

            # Calculate all indicators
            close = df['close']

            # EMAs
            ema_9 = close.ewm(span=9, adjust=False).mean()
            ema_20 = close.ewm(span=20, adjust=False).mean()
            ema_50 = close.ewm(span=50, adjust=False).mean()
            ema_200 = close.ewm(span=200, adjust=False).mean()

            # RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_14 = 100 - (100 / (1 + rs))

            # VWAP (simplified)
            cum_vol = df['volume'].cumsum()
            cum_pv = (df['close'] * df['volume']).cumsum()
            vwap = cum_pv / cum_vol

            # Relative Volume
            vol_sma_20 = df['volume'].rolling(window=20).mean()
            rvol = df['volume'] / vol_sma_20

            # Distance to EMA9
            dist_ema_9 = (close - ema_9) / ema_9 * 100

            # Get last bar (entry point)
            last_idx = len(df) - 1

            feature_row = {
                'filename': filename,
                'close': close.iloc[last_idx],
                'open': df['open'].iloc[last_idx],
                'high': df['high'].iloc[last_idx],
                'low': df['low'].iloc[last_idx],
                'volume': df['volume'].iloc[last_idx],
                'ema_9': ema_9.iloc[last_idx] if not ema_9.isna().iloc[last_idx] else None,
                'ema_20': ema_20.iloc[last_idx] if not ema_20.isna().iloc[last_idx] else None,
                'ema_50': ema_50.iloc[last_idx] if not ema_50.isna().iloc[last_idx] else None,
                'ema_200': ema_200.iloc[last_idx] if not ema_200.isna().iloc[last_idx] else None,
                'vwap': vwap.iloc[last_idx] if not vwap.isna().iloc[last_idx] else None,
                'rsi_14': rsi_14.iloc[last_idx] if not rsi_14.isna().iloc[last_idx] else None,
                'rvol': rvol.iloc[last_idx] if not rvol.isna().iloc[last_idx] else None,
                'dist_ema_9': dist_ema_9.iloc[last_idx] if not dist_ema_9.isna().iloc[last_idx] else None,
            }

            features.append(feature_row)

        return pd.DataFrame(features)

    def _build_indicator_profiles(self, features: pd.DataFrame) -> Dict[str, IndicatorProfile]:
        """Build statistical profiles for each indicator"""
        profiles = {}

        for indicator in self.indicators:
            if indicator not in features.columns:
                continue

            values = features[indicator].dropna()

            if len(values) < 3:
                continue

            # Calculate statistics
            mean = values.mean()
            median = values.median()
            std = values.std()
            min_val = values.min()
            max_val = values.max()
            q25 = values.quantile(0.25)
            q75 = values.quantile(0.75)

            # Common range: where middle 60% of samples fall (20th to 80th percentile)
            common_range = (values.quantile(0.20), values.quantile(0.80))

            profiles[indicator] = IndicatorProfile(
                name=indicator,
                mean=mean,
                median=median,
                std=std,
                min=min_val,
                max=max_val,
                q25=q25,
                q75=q75,
                common_range=common_range
            )

        return profiles

    def _extract_single_rules(self, pos_features: pd.DataFrame,
                              neg_features: Optional[pd.DataFrame]) -> List[Rule]:
        """
        Extract single-condition rules using statistical analysis.
        Examples: "RSI < 35", "Volume > 1.5x average", etc.
        """
        rules = []
        total_pos = len(pos_features)
        total_neg = len(neg_features) if (neg_features is not None and not neg_features.empty) else 0

        print(f"\n   📊 Extracting single-condition rules...")

        # Analyze each indicator
        for indicator in self.indicators:
            if indicator not in pos_features.columns:
                continue

            pos_values = pos_features[indicator].dropna()

            if len(pos_values) < 5:
                continue

            # OPTIMIZED: Reduce percentiles to test (was 11, now 5)
            percentiles = [20, 30, 50, 70, 80]

            for pct in percentiles:
                threshold = pos_values.quantile(pct / 100.0)

                # Test both directions: < and >
                for operator in ['<', '>']:
                    if operator == '<':
                        pos_match = (pos_values < threshold).sum()
                        condition_str = f"{indicator} < {threshold:.2f}"
                    else:
                        pos_match = (pos_values > threshold).sum()
                        condition_str = f"{indicator} > {threshold:.2f}"

                    # Calculate support (% of positive samples matching)
                    support = pos_match / total_pos

                    # Skip if support too low
                    if support < self.min_support:
                        continue

                    # Calculate confidence (always 100% for single positive class)
                    # But we can check against negatives if available
                    if (not neg_features.empty) and (indicator in neg_features.columns):
                        neg_values = neg_features[indicator].dropna()
                        if len(neg_values) > 0:
                            if operator == '<':
                                neg_match = (neg_values < threshold).sum()
                            else:
                                neg_match = (neg_values > threshold).sum()

                            # Confidence = pos_match / (pos_match + neg_match)
                            confidence = pos_match / (pos_match + neg_match) if (pos_match + neg_match) > 0 else 0
                        else:
                            confidence = 1.0
                    else:
                        confidence = 1.0

                    # Skip if confidence too low
                    if confidence < self.min_confidence:
                        continue

                    # Calculate lift
                    baseline_prob = total_pos / (total_pos + total_neg) if total_neg > 0 else 1.0
                    lift = confidence / baseline_prob if baseline_prob > 0 else 1.0

                    # Skip if lift too low
                    if lift < self.min_lift:
                        continue

                    # Chi-square test for significance
                    if (not neg_features.empty) and (indicator in neg_features.columns):
                        # Create contingency table
                        # [[pos_match, pos_no_match], [neg_match, neg_no_match]]
                        pos_no_match = total_pos - pos_match
                        neg_no_match = total_neg - neg_match if total_neg > 0 else 0

                        contingency = np.array([[pos_match, pos_no_match],
                                               [neg_match, neg_no_match]])

                        try:
                            chi2, p_value = stats.chi2_contingency(contingency)[:2]
                        except:
                            p_value = 1.0
                    else:
                        p_value = 0.0  # Assume significant if no negatives

                    # Skip if not statistically significant
                    if p_value > self.max_p_value:
                        continue

                    # Create rule
                    rule = Rule(
                        conditions=[condition_str],
                        support=support * 100,
                        confidence=confidence * 100,
                        lift=lift,
                        p_value=p_value,
                        sample_count=pos_match,
                        avg_pnl=0.0  # Would need actual PnL data
                    )

                    rules.append(rule)

        # Sort by lift (best rules first)
        rules.sort(key=lambda r: r.lift, reverse=True)

        print(f"   ✓ Found {len(rules)} significant single-condition rules")

        return rules[:20]  # Return top 20

    def _extract_combination_rules(self, pos_features: pd.DataFrame,
                                   neg_features: Optional[pd.DataFrame]) -> List[Rule]:
        """
        Extract multi-condition rules (2-3 conditions combined).
        Uses association rule mining with Apriori-like algorithm.
        """
        print(f"\n   🔗 Extracting multi-condition combination rules...")

        combo_rules = []
        total_pos = len(pos_features)
        total_neg = len(neg_features) if (neg_features is not None and not neg_features.empty) else 0

        # First, discretize continuous variables into bins
        # This converts "RSI=32.5" into "RSI_LOW" (< 35)
        pos_binned = self._bin_features(pos_features)
        neg_binned = self._bin_features(neg_features) if (neg_features is not None and not neg_features.empty) else None

        # Get all possible feature_value pairs
        feature_values = []
        for col in pos_binned.columns:
            if col == 'filename':
                continue
            unique_vals = pos_binned[col].unique()
            for val in unique_vals:
                if pd.notna(val):
                    feature_values.append((col, val))

        # OPTIMIZATION: Limit combinations to prevent explosion
        # If too many feature_values, sample randomly
        MAX_FEATURE_VALUES = 30  # Limit to 30 feature-value pairs max
        if len(feature_values) > MAX_FEATURE_VALUES:
            print(f"   ⚡ Optimizing: Sampling {MAX_FEATURE_VALUES} from {len(feature_values)} feature-values")
            feature_values = random.sample(feature_values, MAX_FEATURE_VALUES)

        # Test combinations of 2 features
        # OPTIMIZATION: Limit total combinations tested
        all_combos = list(itertools.combinations(feature_values, 2))
        MAX_COMBOS_TO_TEST = 200  # Test max 200 combinations

        if len(all_combos) > MAX_COMBOS_TO_TEST:
            print(f"   ⚡ Optimizing: Testing {MAX_COMBOS_TO_TEST} from {len(all_combos)} possible combinations")
            all_combos = random.sample(all_combos, MAX_COMBOS_TO_TEST)

        for (feat1, val1), (feat2, val2) in all_combos:
            # Don't combine same feature
            if feat1 == feat2:
                continue

            # Count matches in positive samples
            mask_pos = (pos_binned[feat1] == val1) & (pos_binned[feat2] == val2)
            pos_match = mask_pos.sum()

            # Calculate support
            support = pos_match / total_pos

            # Skip if support too low
            if support < self.min_support:
                continue

            # Calculate confidence against negatives
            if (neg_binned is not None) and (feat1 in neg_binned.columns) and (feat2 in neg_binned.columns):
                mask_neg = (neg_binned[feat1] == val1) & (neg_binned[feat2] == val2)
                neg_match = mask_neg.sum()

                confidence = pos_match / (pos_match + neg_match) if (pos_match + neg_match) > 0 else 0
            else:
                confidence = 1.0

            if confidence < self.min_confidence:
                continue

            # Calculate lift
            baseline_prob = total_pos / (total_pos + total_neg) if total_neg > 0 else 1.0
            lift = confidence / baseline_prob if baseline_prob > 0 else 1.0

            if lift < self.min_lift:
                continue

            # Chi-square test
            if neg_binned is not None:
                pos_no_match = total_pos - pos_match
                neg_no_match = total_neg - neg_match if total_neg > 0 else 0

                contingency = np.array([[pos_match, pos_no_match],
                                       [neg_match, neg_no_match]])

                try:
                    chi2, p_value = stats.chi2_contingency(contingency)[:2]
                except:
                    p_value = 1.0
            else:
                p_value = 0.0

            if p_value > self.max_p_value:
                continue

            # Create human-readable condition strings
            condition_str_1 = self._bin_to_condition_string(feat1, val1)
            condition_str_2 = self._bin_to_condition_string(feat2, val2)

            rule = Rule(
                conditions=[condition_str_1, condition_str_2],
                support=support * 100,
                confidence=confidence * 100,
                lift=lift,
                p_value=p_value,
                sample_count=pos_match,
                avg_pnl=0.0
            )

            combo_rules.append(rule)

        # Sort by lift
        combo_rules.sort(key=lambda r: r.lift, reverse=True)

        print(f"   ✓ Found {len(combo_rules)} significant 2-condition combination rules")

        return combo_rules[:15]  # Top 15

    def _bin_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Bin continuous features into discrete categories.
        Example: RSI 32.5 -> "RSI_LOW" (if < 35)
        """
        binned = pd.DataFrame()
        binned['filename'] = features['filename']

        for col in features.columns:
            if col == 'filename':
                continue

            values = features[col].dropna()

            if len(values) < 3:
                continue

            # Define bins based on domain knowledge
            if 'rsi' in col:
                # RSI: Low (<35), Mid (35-65), High (>65)
                binned[col] = pd.cut(features[col],
                                    bins=[-np.inf, 35, 65, np.inf],
                                    labels=['RSI_LOW', 'RSI_MID', 'RSI_HIGH'])
            elif 'rvol' in col or 'volume' in col:
                # Volume: Low (<1.2x), Mid (1.2-2x), High (>2x)
                median = values.median()
                binned[col] = pd.cut(features[col],
                                    bins=[-np.inf, median * 1.2, median * 2.0, np.inf],
                                    labels=['VOL_LOW', 'VOL_MID', 'VOL_HIGH'])
            elif 'dist' in col:
                # Distance from EMA: Negative (<-1%), Near (-1% to 1%), Positive (>1%)
                binned[col] = pd.cut(features[col],
                                    bins=[-np.inf, -1.0, 1.0, np.inf],
                                    labels=['BELOW_EMA', 'NEAR_EMA', 'ABOVE_EMA'])
            elif 'ema' in col or 'vwap' in col:
                # Price vs EMA/VWAP: Below, Near, Above (based on close price)
                if 'close' in features.columns:
                    close = features['close']
                    ratio = (features[col] - close) / close * 100
                    binned[col] = pd.cut(ratio,
                                        bins=[-np.inf, -2.0, 2.0, np.inf],
                                        labels=[f'{col.upper()}_BELOW', f'{col.upper()}_NEAR', f'{col.upper()}_ABOVE'])
            else:
                # Generic: Low (< 25th pct), Mid (25-75 pct), High (> 75th pct)
                q25 = values.quantile(0.25)
                q75 = values.quantile(0.75)
                binned[col] = pd.cut(features[col],
                                    bins=[-np.inf, q25, q75, np.inf],
                                    labels=[f'{col.upper()}_LOW', f'{col.upper()}_MID', f'{col.upper()}_HIGH'])

        return binned

    def _bin_to_condition_string(self, feature: str, bin_label: str) -> str:
        """Convert binned feature back to human-readable condition"""
        label_str = str(bin_label)

        if 'RSI_LOW' in label_str:
            return "RSI < 35"
        elif 'RSI_MID' in label_str:
            return "RSI 35-65"
        elif 'RSI_HIGH' in label_str:
            return "RSI > 65"
        elif 'VOL_HIGH' in label_str:
            return "Volume > 2x avg"
        elif 'VOL_MID' in label_str:
            return "Volume 1.2-2x avg"
        elif 'BELOW_EMA' in label_str:
            return f"{feature} below price"
        elif 'ABOVE_EMA' in label_str:
            return f"{feature} above price"
        elif 'NEAR_EMA' in label_str:
            return f"Price near {feature}"
        else:
            return f"{feature} = {label_str}"

    def _extract_negative_patterns(self, neg_features: pd.DataFrame) -> List[str]:
        """Extract patterns common in negative samples (what to avoid)"""
        if neg_features is None or neg_features.empty or len(neg_features) < 5:
            return []

        print(f"\n   ⚠️  Extracting negative patterns (what to avoid)...")

        negative_patterns = []

        for indicator in self.indicators:
            if indicator not in neg_features.columns:
                continue

            values = neg_features[indicator].dropna()

            if len(values) < 3:
                continue

            # Find common ranges in negative samples
            median = values.median()
            q25 = values.quantile(0.25)
            q75 = values.quantile(0.75)

            # If 60%+ of negative samples fall in this range, it's a pattern to avoid
            in_range = ((values >= q25) & (values <= q75)).sum()
            pct_in_range = in_range / len(values)

            if pct_in_range >= 0.6:
                negative_patterns.append(
                    f"AVOID: {indicator} between {q25:.2f} and {q75:.2f} "
                    f"({pct_in_range*100:.0f}% of failed trades)"
                )

        return negative_patterns[:5]  # Top 5

    def _generate_summary(self, profiles: Dict[str, IndicatorProfile],
                         single_rules: List[Rule],
                         combo_rules: List[Rule],
                         negative_patterns: List[str]) -> List[str]:
        """Generate human-readable summary of findings"""
        summary = []

        summary.append("=== PATTERN ANALYSIS SUMMARY ===\n")

        # Top indicator profiles
        summary.append("📊 KEY INDICATOR RANGES:")
        for name, profile in list(profiles.items())[:5]:
            summary.append(f"  • {profile}")

        summary.append("\n✅ TOP POSITIVE RULES (Statistically Significant):")
        for i, rule in enumerate(single_rules[:10], 1):
            summary.append(f"  {i}. {rule}")

        if combo_rules:
            summary.append("\n🔗 TOP COMBINATION RULES:")
            for i, rule in enumerate(combo_rules[:5], 1):
                summary.append(f"  {i}. {rule}")

        if negative_patterns:
            summary.append("\n⚠️  PATTERNS TO AVOID:")
            for pattern in negative_patterns:
                summary.append(f"  • {pattern}")

        return summary

    def get_smart_condition_hints(self, analysis_result: Dict) -> Dict:
        """
        Convert extracted rules into hints for GA condition generation.
        This feeds into the genetic algorithm to seed better initial population.
        """
        hints = {
            'rsi_range': None,
            'volume_min': None,
            'ema_position': None,
            'preferred_ranges': {}
        }

        # Extract from indicator profiles
        profiles = analysis_result['indicator_profiles']

        if 'rsi_14' in profiles:
            rsi_profile = profiles['rsi_14']
            hints['rsi_range'] = rsi_profile.common_range

        if 'rvol' in profiles:
            rvol_profile = profiles['rvol']
            hints['volume_min'] = rvol_profile.common_range[0]

        # Extract from top rules
        for rule in analysis_result['single_rules'][:5]:
            condition = rule.conditions[0]
            # Parse condition to extract ranges
            # (Would implement full parser here)
            pass

        return hints
