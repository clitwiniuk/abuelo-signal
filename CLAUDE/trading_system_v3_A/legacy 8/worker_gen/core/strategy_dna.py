import random
from dataclasses import dataclass, field
from typing import List, Union, Literal

# Available indicators in DataManager
INDICATORS = ['close', 'open', 'high', 'low', 'volume', 
              'ema_9', 'ema_20', 'ema_50', 'ema_200', 
              'vwap', 'rsi_14', 'rvol', 'dist_ema_9']

# Comparators
OPERATORS = ['>', '<', '>=', '<=']

@dataclass
class Condition:
    """Represents a single logic rule: Indicator Operator Threshold."""
    left: str  # Indicator name
    operator: str
    right: Union[str, float]  # Indicator name OR numeric constant
    
    def __str__(self):
        val = self.right if isinstance(self.right, (int, float)) else self.right
        return f"{self.left} {self.operator} {val}"

@dataclass
class StrategyGenome:
    """Represents a complete strategy configuration."""
    entry_conditions: List[Condition]
    stop_loss_pct: float
    take_profit_pct: float
    time_limit_bars: int
    
    fitness: float = 0.0
    use_trailing_stop: bool = False
    entry_window_start: int = 0      # Minutes from open (e.g. 0 = 9:30)
    entry_window_end: int = 390      # Minutes from open (e.g. 390 = 16:00)
    
    def __str__(self):
        conditions_str = " AND ".join([str(c) for c in self.entry_conditions])
        exit_mode = "TRAILING" if self.use_trailing_stop else f"TP: {self.take_profit_pct}%"
        time_win = f"TIME: {self.entry_window_start}-{self.entry_window_end}m"
        return f"ENTRY: [{conditions_str}] | {time_win} | SL: {self.stop_loss_pct}% | {exit_mode}"

class DNAFactory:
    """Generates random strategy genomes."""
    
    @staticmethod
    def generate_random_condition() -> Condition:
        # Define groups
        price_indicators = ['close', 'open', 'high', 'low', 'ema_9', 'ema_20', 'ema_50', 'ema_200', 'vwap']
        oscillators = ['rsi_14', 'dist_ema_9', 'rvol']
        
        # Decide type of condition: Price Action or Oscillator
        if random.random() < 0.6:
            # Price Action (e.g. Close > EMA)
            left = random.choice(price_indicators)
            
            # For right side, choose compatible indicator
            right = random.choice(price_indicators)
            
            # Avoid self-comparison
            while right == left:
                right = random.choice(price_indicators)
                
            operator = random.choice(OPERATORS)
            
            # --- LOGIC SANITIZATION ---
            # Prevent impossible/degenerate conditions
            
            # 1. Low vs High
            if (left == 'low' and right == 'high') or (left == 'high' and right == 'low'):
                # Low > High is IMPOSSIBLE
                # Low < High is TAUTOLOGY (almost always true)
                # Ensure we only check for squeeze (Low close to High? No, standard operators don't do that)
                # Ideally, avoid comparing Low and High efficiently unless we want range check
                # Let's force valid direction: High > Low always.
                # If random picked Low > High, swap or change op.
                if left == 'low' and operator in ['>', '>=']:
                    operator = '<' # Low < High (Tautology, but valid code at least)
                elif left == 'high' and operator in ['<', '<=']:
                    operator = '>' 
            
            # 2. Low vs Close/Open (and High vs Close/Open)
            # Low > Close is IMPOSSIBLE (Low is minimum)
            if left == 'low' and operator in ['>', '>='] and right in ['close', 'open']:
                 operator = '<=' # Low <= Close is Tautology
                 left = 'close' # Swap to make it interesting: Close > EMA? No, stay simple.
                 # Better: Don't compare Low > Close.
                 # Let's just swap them: Close > Low (Valid, means not at dead low)
                 left, right = right, left
                 
            # High < Close is IMPOSSIBLE
            if left == 'high' and operator in ['<', '<='] and right in ['close', 'open']:
                 operator = '>='
                 # Swap: Close < High
                 left, right = right, left
                 
        else:
            # Oscillator Logic (e.g. RSI < 30)
            left = random.choice(oscillators)
            operator = random.choice(OPERATORS)
            
            if 'rsi' in left:
                # RSI usually compared to constants 30, 70, 50
                right = random.choice([30, 70, 50, 40, 60])
                # Bias operators for standard mean reversion/trend
                if right <= 40: operator = random.choice(['<', '<=']) # Oversold
                if right >= 60: operator = random.choice(['>', '>=']) # Overbought
                
            elif 'dist' in left:
                 # Dist is % from EMA. -5 to +5 usually.
                 right = round(random.uniform(-3.0, 3.0), 1)
                 
            elif 'rvol' in left:
                 # RVOL > 1.5 etc
                 right = round(random.uniform(1.2, 5.0), 1)
                 operator = '>' # Usually want high volume
            else:
                 right = 0
                 
        return Condition(left, operator, right)
    
    @staticmethod
    def generate_strategy(min_conditions=1, max_conditions=3, use_trailing_stop=False) -> StrategyGenome:
        num_cond = random.randint(min_conditions, max_conditions)
        conditions = [DNAFactory.generate_random_condition() for _ in range(num_cond)]
        
        # REALISTIC Risk Parameters (smallcap optimized)
        # Stop Loss: 2% to 7% (realistic for smallcap volatility)
        sl = round(random.uniform(2.0, 7.0), 2)

        # Take Profit: Risk-Reward ratio 1.5:1 to 4:1 (realistic targets)
        if use_trailing_stop:
            # If trailing stop, use realistic ceiling (not 999%)
            # Set TP as max target before trailing activates
            tp = round(random.uniform(sl * 2.5, sl * 4.0), 2)  # 2.5R to 4R
        else:
            # Fixed TP: 1.5R to 3.5R (realistic risk-reward)
            tp = round(random.uniform(sl * 1.5, sl * 3.5), 2)
        
        time_limit = random.randint(30, 390) # 30 min to full day
        
        # Random Time Window
        # 30% chance of restricted window (Morning or Afternoon)
        # 70% chance of Full Day (0-390)
        win_start = 0
        win_end = 390
        
        r = random.random()
        if r < 0.2:
            # Morning only (0 to 60-120 mins)
            win_end = random.randint(60, 120)
        elif r < 0.3:
            # Power hour/Afternoon (240 to 390)
            win_start = random.randint(240, 300)
            
        return StrategyGenome(conditions, sl, tp, time_limit, fitness=0.0,
                             use_trailing_stop=use_trailing_stop,
                             entry_window_start=win_start,
                             entry_window_end=win_end)

    @staticmethod
    def crossover(parent1: StrategyGenome, parent2: StrategyGenome) -> StrategyGenome:
        """
        Genetic Crossover: Combine two parent strategies to create offspring.
        Takes best characteristics from both parents.
        """
        # Crossover conditions (take mix from both parents)
        num_cond_p1 = len(parent1.entry_conditions)
        num_cond_p2 = len(parent2.entry_conditions)

        # Take random conditions from each parent
        num_from_p1 = random.randint(0, num_cond_p1)
        num_from_p2 = random.randint(0, min(3 - num_from_p1, num_cond_p2))

        child_conditions = []
        if num_from_p1 > 0:
            child_conditions.extend(random.sample(parent1.entry_conditions, num_from_p1))
        if num_from_p2 > 0:
            child_conditions.extend(random.sample(parent2.entry_conditions, num_from_p2))

        # Ensure at least 1 condition
        if not child_conditions:
            child_conditions = [random.choice([parent1.entry_conditions[0], parent2.entry_conditions[0]])]

        # Crossover parameters (average or random choice)
        sl = round((parent1.stop_loss_pct + parent2.stop_loss_pct) / 2.0, 2)
        tp = round((parent1.take_profit_pct + parent2.take_profit_pct) / 2.0, 2)
        time_limit = (parent1.time_limit_bars + parent2.time_limit_bars) // 2

        # Window: choose from one parent randomly
        if random.random() < 0.5:
            win_start = parent1.entry_window_start
            win_end = parent1.entry_window_end
        else:
            win_start = parent2.entry_window_start
            win_end = parent2.entry_window_end

        return StrategyGenome(
            child_conditions, sl, tp, time_limit, fitness=0.0,
            use_trailing_stop=parent1.use_trailing_stop,
            entry_window_start=win_start,
            entry_window_end=win_end
        )

    @staticmethod
    def mutate(genome: StrategyGenome, mutation_rate: float = 0.2) -> StrategyGenome:
        """
        Genetic Mutation: Randomly modify strategy parameters.
        Helps explore new solutions and avoid local optima.
        """
        import copy
        mutated = copy.deepcopy(genome)

        # Mutate conditions (20% chance per condition)
        if random.random() < mutation_rate and mutated.entry_conditions:
            idx = random.randint(0, len(mutated.entry_conditions) - 1)
            mutated.entry_conditions[idx] = DNAFactory.generate_random_condition()

        # Mutate SL (±20%)
        if random.random() < mutation_rate:
            delta = mutated.stop_loss_pct * random.uniform(-0.2, 0.2)
            mutated.stop_loss_pct = round(max(2.0, min(7.0, mutated.stop_loss_pct + delta)), 2)

        # Mutate TP (±20%)
        if random.random() < mutation_rate:
            delta = mutated.take_profit_pct * random.uniform(-0.2, 0.2)
            min_tp = mutated.stop_loss_pct * 1.5
            max_tp = mutated.stop_loss_pct * 4.0
            mutated.take_profit_pct = round(max(min_tp, min(max_tp, mutated.take_profit_pct + delta)), 2)

        # Mutate time limit (±30 mins)
        if random.random() < mutation_rate:
            delta = random.randint(-30, 30)
            mutated.time_limit_bars = max(30, min(390, mutated.time_limit_bars + delta))

        # Mutate time window (10% chance to change)
        if random.random() < mutation_rate * 0.5:
            r = random.random()
            if r < 0.33:
                # Full day
                mutated.entry_window_start = 0
                mutated.entry_window_end = 390
            elif r < 0.66:
                # Morning
                mutated.entry_window_start = 0
                mutated.entry_window_end = random.randint(60, 120)
            else:
                # Afternoon
                mutated.entry_window_start = random.randint(240, 300)
                mutated.entry_window_end = 390

        return mutated

    @staticmethod
    def generate_from_rules(extracted_rules: dict, use_trailing_stop: bool = False) -> StrategyGenome:
        """
        Generate strategy genome seeded from extracted rules.
        Uses statistical insights to create better initial population.

        Args:
            extracted_rules: Output from RuleExtractor.analyze()
            use_trailing_stop: Whether to use trailing stop

        Returns:
            StrategyGenome initialized with rule-based conditions
        """
        import random

        # Extract hints from rules
        single_rules = extracted_rules.get('single_rules', [])
        combo_rules = extracted_rules.get('combo_rules', [])
        profiles = extracted_rules.get('indicator_profiles', {})

        conditions = []

        # Strategy 1: Use top combination rule if available (highest confidence)
        if combo_rules and len(combo_rules) > 0:
            # Pick one of top 3 combo rules randomly
            top_combos = combo_rules[:min(3, len(combo_rules))]
            selected_combo = random.choice(top_combos)

            # Convert combo rule conditions to Condition objects
            for cond_str in selected_combo.conditions:
                condition_obj = DNAFactory._parse_rule_string(cond_str)
                if condition_obj:
                    conditions.append(condition_obj)

        # Strategy 2: Add one single rule if we don't have enough conditions yet
        if len(conditions) < 2 and single_rules:
            top_singles = single_rules[:min(5, len(single_rules))]
            selected_single = random.choice(top_singles)

            condition_obj = DNAFactory._parse_rule_string(selected_single.conditions[0])
            if condition_obj:
                conditions.append(condition_obj)

        # Strategy 3: If still no conditions, use profiles to guide generation
        if not conditions:
            # Use profile-guided random generation
            if 'rsi_14' in profiles:
                rsi_profile = profiles['rsi_14']
                # Use common range
                rsi_threshold = random.uniform(rsi_profile.common_range[0], rsi_profile.common_range[1])
                operator = random.choice(['<', '>'])
                conditions.append(Condition('rsi_14', operator, round(rsi_threshold, 1)))

        # Ensure at least 1 condition
        if not conditions:
            conditions.append(DNAFactory.generate_random_condition())

        # Limit to max 3 conditions
        conditions = conditions[:3]

        # Use realistic parameters (from improved generate_strategy)
        sl = round(random.uniform(2.0, 7.0), 2)

        if use_trailing_stop:
            tp = round(random.uniform(sl * 2.5, sl * 4.0), 2)
        else:
            tp = round(random.uniform(sl * 1.5, sl * 3.5), 2)

        time_limit = random.randint(30, 390)

        # Time window
        win_start = 0
        win_end = 390

        r = random.random()
        if r < 0.2:
            win_end = random.randint(60, 120)
        elif r < 0.3:
            win_start = random.randint(240, 300)

        return StrategyGenome(
            conditions, sl, tp, time_limit, fitness=0.0,
            use_trailing_stop=use_trailing_stop,
            entry_window_start=win_start,
            entry_window_end=win_end
        )

    @staticmethod
    def _parse_rule_string(rule_str: str):
        """
        Parse rule string back into Condition object.
        Example: "RSI < 35" -> Condition('rsi_14', '<', 35)
        """
        import re

        # Clean up the string
        rule_str = rule_str.strip()

        # Patterns to match
        patterns = [
            (r'RSI\s*([<>=]+)\s*([\d.]+)', 'rsi_14'),
            (r'Volume\s*>\s*([\d.]+)x', 'rvol'),
            (r'(?:Price|close)\s*near\s*(\w+)', None),  # Special case
            (r'(\w+)\s*([<>=]+)\s*([\d.]+)', None),  # Generic
        ]

        for pattern, indicator in patterns:
            match = re.search(pattern, rule_str, re.IGNORECASE)
            if match:
                if indicator == 'rsi_14':
                    operator = match.group(1)
                    value = float(match.group(2))
                    return Condition('rsi_14', operator, value)
                elif indicator == 'rvol':
                    value = float(match.group(1))
                    return Condition('rvol', '>', value)
                elif indicator is None and match.lastindex >= 3:
                    # Generic pattern
                    feat = match.group(1).lower()
                    op = match.group(2)
                    val = float(match.group(3))
                    return Condition(feat, op, val)

        # Couldn't parse, return None
        return None
