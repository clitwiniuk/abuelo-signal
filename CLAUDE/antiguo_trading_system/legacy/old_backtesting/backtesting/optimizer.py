# backtesting/optimizer.py
"""
Parameter optimization for strategies.
"""

import itertools
import pandas as pd
from typing import Dict, List, Any, Tuple
import asyncio
import logging
import numpy as np
from datetime import datetime


class ParameterOptimizer:
    """
    Strategy parameter optimization using grid search or random search.
    """
    
    def __init__(self, strategy_class, base_config):
        self.strategy_class = strategy_class
        self.base_config = base_config
        self.logger = logging.getLogger("ParameterOptimizer")
    
    async def grid_search(self, param_grid: Dict[str, List], 
                         symbols: List[str], data_loader,
                         optimization_metric: str = 'sharpe_ratio') -> pd.DataFrame:
        """
        Perform grid search optimization.
        
        Args:
            param_grid: Dictionary of parameter names and their possible values
            symbols: List of symbols to test
            data_loader: Data loading function
            optimization_metric: Metric to optimize ('sharpe_ratio', 'total_return_pct', etc.)
        """
        from .backtest_engine import BacktestEngine
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))
        
        self.logger.info(f"Testing {len(combinations)} parameter combinations")
        
        results = []
        
        # Test each combination
        for i, combination in enumerate(combinations):
            if i % 10 == 0:
                self.logger.info(f"Progress: {i}/{len(combinations)} ({i/len(combinations)*100:.1f}%)")
            
            # Create parameter dict
            params = dict(zip(param_names, combination))
            
            try:
                # Run backtest with these parameters
                result = await self._run_single_backtest(params, symbols, data_loader)
                
                if result:
                    result_dict = {
                        'params': str(params),  # Convert to string for Excel compatibility
                        'sharpe_ratio': result.sharpe_ratio,
                        'total_return_pct': result.total_return_pct,
                        'max_drawdown_pct': result.max_drawdown_pct,
                        'win_rate': result.win_rate,
                        'profit_factor': result.profit_factor,
                        'total_trades': result.total_trades,
                        'cagr': result.cagr,
                        'avg_win': result.avg_win,
                        'avg_loss': result.avg_loss,
                        'calmar_ratio': result.calmar_ratio
                    }
                    
                    # Add individual parameter columns for easier analysis
                    for param_name, param_value in params.items():
                        result_dict[f'param_{param_name}'] = param_value
                    
                    results.append(result_dict)
                
            except Exception as e:
                self.logger.error(f"Error testing parameters {params}: {e}")
        
        # Convert to DataFrame and sort by optimization metric
        results_df = pd.DataFrame(results)
        if not results_df.empty:
            results_df = results_df.sort_values(optimization_metric, ascending=False)
            self.logger.info(f"Optimization completed. Best {optimization_metric}: {results_df.iloc[0][optimization_metric]:.3f}")
        else:
            self.logger.warning("No successful backtests completed")
        
        return results_df
    
    async def _run_single_backtest(self, params: Dict, symbols: List[str], data_loader):
        """Run a single backtest with given parameters"""
        from .backtest_engine import BacktestEngine
        
        try:
            # Create strategy with parameters
            strategy = self.strategy_class(params)
            
            # Create backtest engine
            engine = BacktestEngine(self.base_config)
            engine.add_strategy(strategy)
            engine.set_data_loader(data_loader)
            
            # Run backtest
            result = await engine.run_backtest(symbols)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in single backtest: {e}")
            return None
    
    async def random_search(
        self,
        param_distributions: Dict,
        symbols: List[str],
        data_loader,
        n_iter: int = 100,
        optimization_metric: str = 'sharpe_ratio',
    ) -> pd.DataFrame:
        """
        Perform random search optimization.
        
        Args:
            param_distributions: Dictionary of parameter names and their distributions
            n_iter: Number of random samples to test
            symbols: List of symbols to test
            data_loader: Data loading function
            optimization_metric: Metric to optimize
        """
        results = []
        
        for i in range(n_iter):
            if i % 10 == 0:
                self.logger.info(f"Random search progress: {i}/{n_iter}")
            
            # Sample random parameters
            params = {}
            for param_name, distribution in param_distributions.items():
                if isinstance(distribution, list):
                    # Discrete choice
                    params[param_name] = np.random.choice(distribution)
                elif isinstance(distribution, tuple) and len(distribution) == 2:
                    # Continuous uniform distribution
                    min_val, max_val = distribution
                    if isinstance(min_val, int) and isinstance(max_val, int):
                        params[param_name] = np.random.randint(min_val, max_val + 1)
                    else:
                        params[param_name] = np.random.uniform(min_val, max_val)
            
            try:
                # Run backtest
                result = await self._run_single_backtest(params, symbols, data_loader)
                
                if result:
                    result_dict = {
                        'params': str(params),
                        'sharpe_ratio': result.sharpe_ratio,
                        'total_return_pct': result.total_return_pct,
                        'max_drawdown_pct': result.max_drawdown_pct,
                        'win_rate': result.win_rate,
                        'profit_factor': result.profit_factor,
                        'total_trades': result.total_trades,
                        'cagr': result.cagr
                    }
                    
                    for param_name, param_value in params.items():
                        result_dict[f'param_{param_name}'] = param_value
                    
                    results.append(result_dict)
                    
            except Exception as e:
                self.logger.error(f"Error in random search iteration {i}: {e}")
        
        results_df = pd.DataFrame(results)
        if not results_df.empty:
            results_df = results_df.sort_values(optimization_metric, ascending=False)
        
        return results_df
    
    def analyze_parameter_sensitivity(self, results_df: pd.DataFrame, 
                                    target_metric: str = 'sharpe_ratio') -> Dict:
        """Analyze parameter sensitivity"""
        if results_df.empty:
            return {}
        
        param_columns = [col for col in results_df.columns if col.startswith('param_')]
        sensitivity_analysis = {}
        
        for param_col in param_columns:
            param_name = param_col.replace('param_', '')
            
            # Group by parameter value and calculate mean metric
            param_impact = results_df.groupby(param_col)[target_metric].agg(['mean', 'std', 'count'])
            
            sensitivity_analysis[param_name] = {
                'impact': param_impact.to_dict(),
                'correlation': results_df[param_col].corr(results_df[target_metric]),
                'best_value': results_df.loc[results_df[target_metric].idxmax(), param_col],
                'value_range': (results_df[param_col].min(), results_df[param_col].max())
            }
        
        return sensitivity_analysis


# Example usage functions
async def example_macdv_backtest_with_data():
    """Example of complete MACDV backtest with your data structure"""
    from strategies.macdv_strategy import MACDVStrategy
    from .backtest_engine import BacktestEngine, BacktestConfig
    from .data_loader import BacktestDataLoader
    from .analysis import BacktestAnalyzer
    
    # 1. Configure backtest for 5-minute data
    config = BacktestConfig(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
        initial_capital=10000.0,
        commission_per_trade=1.0,
        commission_pct=0.001,
        slippage_pct=0.001,
        max_positions=3,
        risk_per_trade=0.02,
        data_frequency="5min"  # Specify 5-minute data
    )
    
    # 2. Set up data loader for your data folder
    data_loader = BacktestDataLoader()
    
    # Create data loading function pointing to your data folder
    def load_symbol_data(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Load data from your local data folder"""
        data_folder = "data"  # Your data folder
        data_dict = data_loader.load_data_folder(data_folder, [symbol], start, end)
        return data_dict.get(symbol, pd.DataFrame())
    
    # 3. Create and run backtest
    engine = BacktestEngine(config)
    
    # Add MACDV strategy with optimized parameters for 5-min data
    macdv_params = {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'stop_loss_pct': 0.03,
        'take_profit_pct': 0.06,
        'min_conditions': 4,
        'volume_threshold': 1.5,
        'ma_short': 10,
        'ma_long': 21,
        'max_hold_hours': 4  # Shorter for 5-min data
    }
    
    strategy = MACDVStrategy(macdv_params)
    engine.add_strategy(strategy)
    engine.set_data_loader(load_symbol_data)
    
    # 4. Run backtest on your symbols
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]  # Adjust to your available symbols
    results = await engine.run_backtest(symbols)
    
    # 5. Comprehensive analysis
    analyzer = BacktestAnalyzer(results)
    analyzer.print_summary_report()
    analyzer.plot_equity_curve()
    analyzer.plot_trade_analysis()
    analyzer.plot_monthly_heatmap()
    
    # 6. Export results
    analyzer.export_results_to_excel("macdv_backtest_results.xlsx")
    
    return results, analyzer


async def example_parameter_optimization_5min():
    """Example of parameter optimization for 5-minute data"""
    from strategies.macdv_strategy import MACDVStrategy
    from .backtest_engine import BacktestConfig
    from .data_loader import BacktestDataLoader
    
    # Base configuration for 5-minute data
    base_config = BacktestConfig(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 6, 30),  # Shorter period for faster optimization
        initial_capital=10000.0,
        commission_per_trade=1.0,
        commission_pct=0.001,
        slippage_pct=0.001,
        max_positions=3,
        risk_per_trade=0.02,
        data_frequency="5min"
    )
    
    # Parameter grid optimized for 5-minute timeframe
    param_grid = {
        'macd_fast': [8, 12, 16, 20],
        'macd_slow': [21, 26, 30, 34],
        'stop_loss_pct': [0.02, 0.03, 0.04, 0.05],
        'take_profit_pct': [0.04, 0.06, 0.08, 0.10],
        'min_conditions': [3, 4, 5],
        'volume_threshold': [1.2, 1.5, 2.0],
        'max_hold_hours': [2, 4, 6, 8]  # Shorter holding periods for 5-min data
    }
    
    # Set up data loader
    data_loader = BacktestDataLoader()
    def load_data(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        data_dict = data_loader.load_data_folder("data", [symbol], start, end)
        return data_dict.get(symbol, pd.DataFrame())
    
    # Run optimization
    optimizer = ParameterOptimizer(MACDVStrategy, base_config)
    symbols = ["AAPL", "GOOGL", "MSFT"]  # Adjust to your available symbols
    
    print("Starting parameter optimization...")
    results_df = await optimizer.grid_search(param_grid, symbols, load_data, 'sharpe_ratio')
    
    # Save optimization results
    results_df.to_excel("macdv_optimization_results.xlsx", index=False)
    
    # Analyze parameter sensitivity
    sensitivity = optimizer.analyze_parameter_sensitivity(results_df)
    
    print("\nOptimization Results:")
    print("=" * 50)
    print("Best Parameters:")
    if not results_df.empty:
        best_row = results_df.iloc[0]
        for col in results_df.columns:
            if col.startswith('param_'):
                print(f"{col.replace('param_', '')}: {best_row[col]}")
        
        print(f"\nBest Performance:")
        print(f"Sharpe Ratio: {best_row['sharpe_ratio']:.3f}")
        print(f"Total Return: {best_row['total_return_pct']:.2f}%")
        print(f"Max Drawdown: {best_row['max_drawdown_pct']:.2f}%")
        print(f"Win Rate: {best_row['win_rate']:.2f}%")
    
    return results_df, sensitivity


if __name__ == "__main__":
    # Run example backtest
    import asyncio
    
    # Uncomment to run backtest
    # results, analyzer = asyncio.run(example_macdv_backtest_with_data())
    
    # Uncomment to run optimization
    # opt_results, sensitivity = asyncio.run(example_parameter_optimization_5min())
    
    pass