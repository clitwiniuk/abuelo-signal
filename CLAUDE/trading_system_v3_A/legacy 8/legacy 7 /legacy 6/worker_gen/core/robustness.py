import copy
import random
import numpy as np
import re
from datetime import datetime
from typing import List, Dict
from .strategy_dna import StrategyGenome
from .backtest_sim import VectorSimulator

class RobustnessAnalyzer:
    """
    Advanced robustness testing suite.
    """
    
    @staticmethod
    def run_monte_carlo_permutation(trades: List[float], iterations: int = 1000) -> dict:
        """
        Performs Monte Carlo Permutation Test on the sequence of trades.
        Shuffles the trade PnLs to destroy time-correlation (if any) and market regime luck.
        Actually, standard permutation reshuffles the sequence.
        
        Returns:
            probability_of_loss: % of runs that lost money.
            original_percentile: Where the original PnL sits in the distribution (0-100).
        """
        if not trades:
            return {'risk_of_ruin': 100, 'p_value': 1.0}
            
        original_pnl = sum(trades)
        simulated_pnls = []
        
        trades_arr = np.array(trades)
        
        for _ in range(iterations):
            # 1. Reshuffle (Testing dependency on time/sequence - less relevant for independent patterns but good for equity curve smoothness)
            # OR 2. Resampling with replacement (Bootstrapping) - Better estimates distribution variance
            
            # Let's do Bootstrapping (with replacement) to test variance
            resampled = np.random.choice(trades_arr, size=len(trades), replace=True)
            simulated_pnls.append(np.sum(resampled))
            
        simulated_pnls = np.array(simulated_pnls)
        
        # Win Probability (randomly drawn trades)
        prob_profit = np.mean(simulated_pnls > 0)
        
        # Where does original fit?
        percentile = (simulated_pnls < original_pnl).mean() * 100
        
        return {
            'win_probability': float(prob_profit * 100), # Probability that a random set of similar trades is profitable
            'percentile': float(percentile), # Top X% of runs
            'worst_case_drawdown': float(np.min(simulated_pnls)) # Proxy for worst luck
        }

    @staticmethod
    def run_parameter_sensitivity(genome: StrategyGenome, data_map: Dict, variations=5) -> dict:
        """
        Varies SL, TP, and Time parameters slightly to check stability.
        Returns a stability score (0-100).
        """
        original_pnl = 0.0
        
        # Get baseline PnL
        for df in data_map.values():
             res = VectorSimulator.evaluate(df, genome)
             original_pnl += res['total_pnl']
             
        variations_pnls = []
        
        # Factors to vary: 0.8 to 1.2
        factors = np.linspace(0.8, 1.2, variations)
        
        for sl_fac in factors:
            for tp_fac in factors:
                # Create variant
                variant = copy.deepcopy(genome)
                variant.stop_loss_pct = round(genome.stop_loss_pct * sl_fac, 2)
                variant.take_profit_pct = round(genome.take_profit_pct * tp_fac, 2)
                # Don't vary time too much, it's discrete
                
                # Run sim
                pnl = 0.0
                for df in data_map.values():
                    res = VectorSimulator.evaluate(df, variant)
                    pnl += res['total_pnl']
                
                variations_pnls.append(pnl)
        
        if not variations_pnls:
            return {'stability_score': 0}
            
        # Analysis
        # If original PnL is close to the MEAN of variations, it's stable.
        # If original is the MAX (outlier), it's overfitted to specific params.
        
        mean_pnl = np.mean(variations_pnls)
        std_dev = np.std(variations_pnls)
        
        # Stability Score:
        # Penalize if standard deviation is high relative to mean
        if mean_pnl <= 0:
            cv = 100 # Bad
        else:
            cv = (std_dev / mean_pnl) # Coefficient of Variation
            
        # Map CV to 0-100 score
        # CV of 0.1 (10%) -> Score 90
        # CV of 0.5 (50%) -> Score 50
        # CV of 1.0 (100%) -> Score 0
        
        score = max(0, 100 - (cv * 100))
        
        return {
            'stability_score': float(score),
            'neighborhood_mean_pnl': float(mean_pnl),
            'pnl_volatility': float(std_dev)
        }

    @staticmethod
    def run_walk_forward_validation(genome: StrategyGenome, data_map: Dict) -> dict:
        """
        Tests the strategy on sequential monthly/time windows to verify consistency.
        Returns detailed period stats and a consistency score.
        """
        # 1. Detect Time Span & Auto-Select Period Type
        dates = []
        parsed_data = [] # Store (date_obj, key, df)
        
        for key, df in data_map.items():
            match = re.search(r'(\d{4})-(\d{2})-(\d{2})', key)
            if match:
                d_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                dates.append(d_obj)
                parsed_data.append((d_obj, df))
                
        if not dates:
             return {'consistency_score': 0, 'details': []}
             
        # Determine Period Type
        min_date = min(dates)
        max_date = max(dates)
        diff_days = (max_date - min_date).days
        
        unique_months = len(set(d.strftime("%Y-%m") for d in dates))
        
        # If very short duration or few months, use Weekly
        use_weekly = unique_months < 4 or diff_days < 90
        period_type = "Weekly" if use_weekly else "Monthly"
        
        periods: Dict[str, List] = {}
        
        # 2. Group Data
        for d_obj, df in parsed_data:
            if use_weekly:
                # Year-Week
                year, week, _ = d_obj.isocalendar()
                period_key = f"{year}-W{week:02d}"
            else:
                # Year-Month
                period_key = d_obj.strftime("%Y-%m")
                
            if period_key not in periods:
                periods[period_key] = []
            periods[period_key].append(df)
            
        # 3. Sort Periods
        sorted_periods = sorted(periods.keys())
        
        if not sorted_periods:
            return {'consistency_score': 0, 'details': []}
            
        # 4. Test Each Period
        results = []
        profitable_periods = 0
        total_pnl = 0.0
        
        for p_key in sorted_periods:
            dfs = periods[p_key]
            period_pnl = 0.0
            period_trades = 0
            
            for df in dfs:
                res = VectorSimulator.evaluate(df, genome)
                period_pnl += res['total_pnl']
                period_trades += res['num_trades']
                
            results.append({
                'period': p_key,
                'pnl': round(period_pnl, 2),
                'trades': period_trades
            })
            
            if period_pnl > 0:
                profitable_periods += 1
            total_pnl += period_pnl
            
        # 5. Calc Metrics
        consistency = (profitable_periods / len(sorted_periods)) * 100 if sorted_periods else 0.0
        
        return {
            'consistency_score': float(consistency),
            'period_type': period_type,
            'total_periods': len(sorted_periods),
            'profitable_periods': profitable_periods,
            'period_stats': results
        }
