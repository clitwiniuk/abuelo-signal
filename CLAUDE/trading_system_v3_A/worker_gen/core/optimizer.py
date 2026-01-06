import random
from typing import Dict, List, Optional
import pandas as pd
from .data_manager import DataManager
from .strategy_dna import DNAFactory, StrategyGenome
from .backtest_sim import VectorSimulator
from .robustness import RobustnessAnalyzer
from .rule_extractor import RuleExtractor

class Optimizer:
    """
    Core engine that searches for the best strategy.
    """
    
    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
        
    def optimize(self, iterations: int = 1000, use_trailing_stop: bool = False, smart_optimize: bool = False) -> tuple[Optional[StrategyGenome], Dict]:
        """
        Runs the search loop with In-Sample (IS) training and Out-of-Sample (OOS) validation.
        """
        data = self.dm.get_data()
        if not data:
            print("❌ No data to optimize on.")
            return None, {}

        # --- DATA VALIDATION: Minimum Samples Required ---
        MIN_SAMPLES_REQUIRED = 20  # Need at least 20 labeled samples
        MIN_BLIND_SAMPLES = 5  # Need at least 5 samples for blind test

        if len(data) < MIN_SAMPLES_REQUIRED:
            print(f"❌ INSUFFICIENT DATA: {len(data)} samples found, need at least {MIN_SAMPLES_REQUIRED}")
            print(f"   Recommendation: Label more examples of this pattern (need {MIN_SAMPLES_REQUIRED - len(data)} more)")
            return None, {
                'error': 'insufficient_data',
                'samples_found': len(data),
                'samples_required': MIN_SAMPLES_REQUIRED
            }
            
        # 1. Split Data (Train/Test) for Robustness
        # Sort keys to ensure temporal split if filenames contain dates (standard format)
        sorted_keys = sorted(data.keys())
        split_idx = int(len(sorted_keys) * 0.7)
        
        # Ensure at least 1 file in each if possible
        if len(sorted_keys) >= 2:
             # GLOBAL TIME SPLIT FOR BLIND TESTING
             # We must sort by Date, not just by Key string (to avoid Symbol grouping)
             # Expected format: SYMBOL_YYYY-MM-DD.csv
             
             import re
             from datetime import datetime
             
             date_map = []
             unknown_date_keys = []
             
             for k in data.keys():
                 match = re.search(r'(\d{4})-(\d{2})-(\d{2})', k)
                 if match:
                     d_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                     d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                     date_map.append((d_obj, k))
                 else:
                     unknown_date_keys.append(k)
             
             # Sort by Date
             date_map.sort(key=lambda x: x[0])
             
             # Split Time-Based (Last 20% of DATES)
             # We split by unique dates to avoid cutting a single day in half
             unique_dates = sorted(list(set(d for d, k in date_map)))
             split_date_idx = int(len(unique_dates) * 0.8) # 80% Train, 20% Blind
             
             if split_date_idx == len(unique_dates): # If tiny data
                 split_date_idx = max(0, len(unique_dates) - 1)
                 
             split_date = unique_dates[split_date_idx] if unique_dates else None
             
             train_keys = []
             blind_keys = [] # Formerly test_keys
             
             for d, k in date_map:
                 if d < split_date:
                     train_keys.append(k)
                 else:
                     blind_keys.append(k)
                     
             # Add unknown dates to train (assume old?)
             train_keys.extend(unknown_date_keys)
             
             # FALLBACK: If split failed (e.g. all on same day), fall back to simple split
             if not blind_keys and len(train_keys) > 1:
                  split_idx = int(len(train_keys) * 0.8)
                  blind_keys = train_keys[split_idx:]
                  train_keys = train_keys[:split_idx]
                  
        else:
             print("⚠️  Warning: Not enough data for Train/Test split. Promoting robust overfitting risk.")
             train_keys = sorted_keys
             blind_keys = []
             
        # Identify negative samples in Train Set
        # Negative samples are ONLY for Training context (to learn what NOT to do)
        # We generally do not want them in Blind Test (it's confusing to report PnL on them unless we invert it)
        # So we force ALL Negatives into Train Keys
        
        # 1. Separate Negatives from Blind Keys
        neg_blind = [k for k in blind_keys if k.startswith("NEG_")]
        pos_blind = [k for k in blind_keys if not k.startswith("NEG_")]
        
        # Move Negatives back to Train (we need them for evolutionary pressure)
        blind_keys = pos_blind
        train_keys.extend(neg_blind)

        # Identify negative samples in Train Set
        pos_train_keys = [k for k in train_keys if not k.startswith("NEG_")]
        neg_train_keys = [k for k in train_keys if k.startswith("NEG_")]

        # --- VALIDATION: Check minimum samples after split ---
        if len(blind_keys) < MIN_BLIND_SAMPLES:
            print(f"❌ INSUFFICIENT BLIND TEST DATA: {len(blind_keys)} samples, need at least {MIN_BLIND_SAMPLES}")
            print(f"   Total samples: {len(data)}, but temporal split left too few for validation")
            print(f"   Recommendation: Label more recent examples (need {MIN_BLIND_SAMPLES - len(blind_keys)} more in future dates)")
            return None, {
                'error': 'insufficient_blind_data',
                'blind_samples': len(blind_keys),
                'required_blind': MIN_BLIND_SAMPLES
            }

        if len(pos_train_keys) < 10:
            print(f"❌ INSUFFICIENT POSITIVE TRAINING DATA: {len(pos_train_keys)} samples, need at least 10")
            return None, {
                'error': 'insufficient_positive_training',
                'positive_samples': len(pos_train_keys)
            }

        print(f"   Train Set: {len(train_keys)} ({len(neg_train_keys)} Neg / {len(pos_train_keys)} Pos)")
        print(f"   Blind Test Set (Hold-out): {len(blind_keys)} files (Future Data)")

        # --- RULE EXTRACTION (Pre-GA Analysis) ---
        print("\n" + "="*70)
        print("PHASE 1: RULE EXTRACTION & PATTERN ANALYSIS")
        print("="*70)

        # Extract rules from training data ONLY (never use blind test for training!)
        train_data_map = {k: data[k] for k in train_keys}

        rule_extractor = RuleExtractor(
            min_support=0.30,  # Rule must apply to 30%+ of samples
            min_confidence=0.65,  # 65%+ confidence
            min_lift=1.15,  # 15% better than random
            max_p_value=0.05  # 95% statistical significance
        )

        extracted_rules = rule_extractor.analyze(train_data_map)

        # Print summary
        print("\n📋 EXTRACTED RULES SUMMARY:")
        for line in extracted_rules['summary']:
            print(line)

        # Store extracted rules in stats for frontend display
        stats = {'extracted_rules': extracted_rules}

        print("\n" + "="*70)
        print("PHASE 2: GENETIC ALGORITHM OPTIMIZATION")
        print("="*70)

        # --- GENETIC ALGORITHM SETUP ---
        POPULATION_SIZE = 30  # Maintain population of 30 strategies (reduced for speed)
        ELITE_SIZE = 6  # Keep top 6 strategies
        TOURNAMENT_SIZE = 3  # Tournament selection
        CROSSOVER_RATE = 0.7  # 70% of offspring via crossover
        MUTATION_RATE = 0.2  # 20% mutation rate

        # Helper function to evaluate fitness
        def evaluate_fitness(genome: StrategyGenome) -> float:
            total_weighted_pnl = 0.0
            total_trades = 0

            for name in train_keys:
                df = data[name]
                res = VectorSimulator.evaluate(df, genome)

                if res['num_trades'] > 0:
                    if name.startswith("NEG_"):
                        # PENALTY! We traded on a negative sample.
                        penalty = res['num_trades'] * 5.0  # Heavy penalty per trade
                        total_weighted_pnl -= penalty
                    else:
                        total_weighted_pnl += res['total_pnl']
                        total_trades += res['num_trades']

            # Reject if inactive
            if total_trades < 5:
                return -1000

            # Core Fitness: Total PnL with complexity penalty
            fitness = total_weighted_pnl
            penalty_factor = 1.0 - (0.05 * (len(genome.entry_conditions) - 1))
            fitness *= penalty_factor

            return fitness

        # Initialize Population (Generation 0) - HYBRID APPROACH
        print(f"🧬 Initializing population of {POPULATION_SIZE} strategies...")
        print(f"   • 40% rule-based (seeded from extracted patterns)")
        print(f"   • 60% random (exploration)")

        population = []

        # Part 1: Rule-based population (40%)
        rule_based_count = int(POPULATION_SIZE * 0.4)
        for i in range(rule_based_count):
            try:
                genome = DNAFactory.generate_from_rules(extracted_rules, use_trailing_stop=use_trailing_stop)
                population.append(genome)
            except Exception as e:
                # Fallback to random if rule generation fails
                print(f"   ⚠️  Rule-based generation failed: {e}, using random")
                genome = DNAFactory.generate_strategy(use_trailing_stop=use_trailing_stop)
                population.append(genome)

        # Part 2: Random population (60%) for exploration
        random_count = POPULATION_SIZE - rule_based_count
        for i in range(random_count):
            genome = DNAFactory.generate_strategy(use_trailing_stop=use_trailing_stop)
            population.append(genome)

        # Evaluate initial population
        for genome in population:
            genome.fitness = evaluate_fitness(genome)

        best_genome = None
        best_is_score = -float('inf')
        patience_counter = 0
        generations = iterations // POPULATION_SIZE  # Convert iterations to generations

        print(f"🚀 Running {generations} generations (Population: {POPULATION_SIZE})...")

        # --- GENETIC ALGORITHM LOOP ---
        for generation in range(generations):
            # Sort population by fitness (best first)
            population.sort(key=lambda g: g.fitness, reverse=True)

            # Track best
            if population[0].fitness > best_is_score:
                # Check stability if smart mode is on
                is_stable_enough = True

                if smart_optimize:
                    train_data_map = {k: data[k] for k in train_keys}
                    sensitivity = RobustnessAnalyzer.run_parameter_sensitivity(
                        population[0], train_data_map, variations=3
                    )

                    if sensitivity['stability_score'] < 60:
                        is_stable_enough = False

                if is_stable_enough:
                    best_is_score = population[0].fitness
                    best_genome = population[0]
                    patience_counter = 0
                    print(f"  Gen {generation}: New best! Fitness={best_is_score:.2f}")

            # Smart Early Stopping
            if smart_optimize and best_genome:
                patience_counter += 1
                if patience_counter > 20:  # 20 generations without improvement
                    print(f"🛑 Smart Stop: No better stable strategy in 20 generations. Stopping at gen {generation}.")
                    break

            # --- SELECTION AND BREEDING ---
            # 1. Elitism: Keep best strategies
            next_population = population[:ELITE_SIZE]

            # 2. Generate offspring to fill population
            while len(next_population) < POPULATION_SIZE:
                # Tournament selection (pick best from random subset)
                def tournament_select():
                    tournament = random.sample(population, TOURNAMENT_SIZE)
                    return max(tournament, key=lambda g: g.fitness)

                parent1 = tournament_select()
                parent2 = tournament_select()

                # Crossover
                if random.random() < CROSSOVER_RATE:
                    child = DNAFactory.crossover(parent1, parent2)
                else:
                    # Clone parent
                    child = random.choice([parent1, parent2])

                # Mutation
                child = DNAFactory.mutate(child, mutation_rate=MUTATION_RATE)

                # Evaluate child
                child.fitness = evaluate_fitness(child)
                next_population.append(child)

            population = next_population

        if not best_genome:
            print("❌ No profitable strategy found in training.")
            return None, {}
            
        print(f"\n🏆 Best Candidate (In-Sample): PnL={best_is_score:.2f}% | {best_genome}")

        # --- CALCULATE IS METRICS ---
        all_is_trades = []
        neg_entries = 0  # Count entries on negative samples
        neg_total = 0    # Total negative samples tested

        for name in train_keys:
             res = VectorSimulator.evaluate(data[name], best_genome)

             # Track negative pattern avoidance
             if name.startswith("NEG_"):
                 neg_total += 1
                 if res['num_trades'] > 0:
                     neg_entries += res['num_trades']

             if 'trades' in res:
                 all_is_trades.extend(res['trades'])

        # Calculate negative avoidance rate
        neg_avoidance_rate = 100.0 * (1 - (neg_entries / neg_total)) if neg_total > 0 else 100.0
        print(f"\n📊 Negative Pattern Avoidance: {neg_avoidance_rate:.1f}% ({neg_total - neg_entries}/{neg_total} avoided)")
        if neg_entries > 0:
            print(f"   ⚠️  WARNING: Strategy triggered {neg_entries} times on {neg_total} negative samples")

        # Update stats with base metrics (preserve extracted_rules from earlier)
        stats.update({
            'is_pnl': best_is_score,
            'is_trades': len(all_is_trades),
            'blind_pnl': 0.0,
            'blind_trades': 0,
            'robustness': 'unknown_no_blind',
            'stability_score': 0,
            'monte_carlo_prob': 0,
            'negative_avoidance_rate': neg_avoidance_rate,
            'negative_entries': neg_entries,
            'negative_total': neg_total
        })

        # --- BLIND TEST VALIDATION (Hold-out) ---
        if not blind_keys:
            print("⚠️  Skipping Blind Test (no future data). Risk of Overfitting: HIGH")
            return best_genome, stats
            
        print("\n🔍 Running Blind Test (Hold-out Validation)...")
        blind_pnl = 0.0
        blind_trades = 0
        
        for name in blind_keys:
            df = data[name]
            res = VectorSimulator.evaluate(df, best_genome)
            blind_pnl += res['total_pnl']
            blind_trades += res['num_trades']
            
        print(f"   Blind Test Result: PnL={blind_pnl:.2f}% | Trades={blind_trades}")
        
        # Robustness Check
        norm_is_pnl = best_is_score / len(train_keys)
        norm_blind_pnl = blind_pnl / len(blind_keys)
        
        # --- ADVANCED ROBUSTNESS ---
        print("\n🔬 Running Advanced Robustness (Sensitivity & Monte Carlo)...")
        
        # 1. Parameter Sensitivity (Neighborhood check)
        train_data_map = {k: data[k] for k in train_keys}
        sensitivity = RobustnessAnalyzer.run_parameter_sensitivity(best_genome, train_data_map)
        print(f"   Stability Score: {sensitivity['stability_score']:.1f}/100")
        
        # 2. Monte Carlo (Bootstrapping)
        # using all_is_trades calculated earlier
        monte_carlo = RobustnessAnalyzer.run_monte_carlo_permutation(all_is_trades)
        print(f"   Monte Carlo Win Prob: {monte_carlo['win_probability']:.1f}%")

        stats['blind_pnl'] = blind_pnl
        stats['blind_trades'] = blind_trades
        stats['stability_score'] = sensitivity['stability_score']
        stats['monte_carlo_prob'] = monte_carlo['win_probability']

        # --- ENHANCED ROBUSTNESS THRESHOLDS (Stricter) ---
        # Multiple criteria must pass for approval

        # Criterion 1: Blind Test PnL
        blind_pnl_ok = blind_pnl > 0 and norm_blind_pnl >= (norm_is_pnl * 0.7)  # Within 70% of IS

        # Criterion 2: Minimum Blind Trades
        min_blind_trades_ok = blind_trades >= 3  # Need at least 3 trades in blind test

        # Criterion 3: Stability Score (Parameter sensitivity)
        stability_ok = sensitivity['stability_score'] >= 70  # At least 70/100

        # Criterion 4: Monte Carlo Win Probability
        monte_carlo_ok = monte_carlo['win_probability'] >= 70  # At least 70% confidence

        # Combined Robustness Status
        if blind_pnl < 0 and best_is_score > 0:
            stats['robustness_status'] = 'fail_overfit'
            stats['robustness_reason'] = 'Negative PnL in blind test - Deep overfitting'
            print("❌ FAIL: Strategy failed in Blind Test (Negative PnL). Deep Overfitting detected.")
            print("   Recommendation: Do NOT use this strategy. It memorized past data.")

        elif not min_blind_trades_ok:
            stats['robustness_status'] = 'fail_inactive'
            stats['robustness_reason'] = f'Too few trades in blind test ({blind_trades} < 3)'
            print(f"❌ FAIL: Strategy too inactive in Blind Test ({blind_trades} trades)")
            print("   Recommendation: Strategy may not trigger reliably on new data.")

        elif not stability_ok:
            stats['robustness_status'] = 'fail_unstable'
            stats['robustness_reason'] = f'Low stability score ({sensitivity["stability_score"]:.0f} < 70)'
            print(f"❌ FAIL: Strategy unstable (Stability: {sensitivity['stability_score']:.0f}/100)")
            print("   Recommendation: Parameters are too sensitive - results vary wildly.")

        elif not monte_carlo_ok:
            stats['robustness_status'] = 'warning_low_confidence'
            stats['robustness_reason'] = f'Low Monte Carlo confidence ({monte_carlo["win_probability"]:.0f}% < 70%)'
            print(f"⚠️  WARNING: Low confidence (Monte Carlo: {monte_carlo['win_probability']:.0f}%)")
            print("   Recommendation: Results may be due to luck, not edge.")

        elif not blind_pnl_ok:
            stats['robustness_status'] = 'warning_drop'
            stats['robustness_reason'] = f'Performance drop (IS: {norm_is_pnl:.1f}% vs Blind: {norm_blind_pnl:.1f}%)'
            print(f"⚠️  WARNING: Performance dropped in Blind Test (Avg IS: {norm_is_pnl:.2f}% vs Avg Blind: {norm_blind_pnl:.2f}%)")
            print("   Recommendation: Strategy may work but with reduced edge.")

        else:
            stats['robustness_status'] = 'pass'
            stats['robustness_reason'] = 'All robustness criteria passed'
            print("✅ PASS: Strategy passed all robustness checks!")
            print(f"   ✓ Blind PnL: {blind_pnl:.2f}% ({norm_blind_pnl:.1f}% avg)")
            print(f"   ✓ Stability: {sensitivity['stability_score']:.0f}/100")
            print(f"   ✓ Monte Carlo: {monte_carlo['win_probability']:.0f}% confidence")
            print(f"   ✓ Blind Trades: {blind_trades}")

        return best_genome, stats
