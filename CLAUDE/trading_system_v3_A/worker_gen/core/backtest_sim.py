import pandas as pd
import numpy as np
from .strategy_dna import StrategyGenome

class VectorSimulator:
    """
    Fast simulator that evaluates a strategy against a standardized dataframe.
    """
    
    @staticmethod
    def evaluate(df: pd.DataFrame, strategy: StrategyGenome) -> dict:
        """
        Runs the strategy on the dataframe.
        Returns metrics: {'total_pnl': float, 'num_trades': int, 'win_rate': float}
        """
        # 1. Calculate Entry Signal Vector
        # Start with all True
        entry_mask = pd.Series(True, index=df.index)
        
        for cond in strategy.entry_conditions:
            left_series = df[cond.left]
            
            if isinstance(cond.right, str):
                right_val = df[cond.right]
            else:
                right_val = cond.right
                
            if cond.operator == '>':
                mask = left_series > right_val
            elif cond.operator == '<':
                mask = left_series < right_val
            elif cond.operator == '>=':
                mask = left_series >= right_val
            elif cond.operator == '<=':
                mask = left_series <= right_val
            else:
                mask = pd.Series(False, index=df.index)
                
            entry_mask = entry_mask & mask
            
        # Time Window Filter
        # Calculate minutes from open (assuming 9:30 AM ET)
        # This assumes data is already localized or standard. 
        # For simplicity, we assume timestamp is available.
        if hasattr(df, 'timestamp') or 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'])
            # Convert to minutes from midnight
            minutes_of_day = ts.dt.hour * 60 + ts.dt.minute
            # Market Open is 9:30 = 570 minutes
            minutes_from_open = minutes_of_day - 570
            
            time_mask = (minutes_from_open >= strategy.entry_window_start) & (minutes_from_open <= strategy.entry_window_end)
            entry_mask = entry_mask & time_mask
            
        # If no signals, return zero
        possible_entries = df[entry_mask]
        if possible_entries.empty:
            return {'total_pnl': 0.0, 'num_trades': 0, 'win_rate': 0.0}
            
        # 2. Simulate Trades Loop
        # We cannot just take all true signals because we might be in a trade.
        # We need to iterate.
        
        trades = []
        i = 0
        n = len(df)
        
        # Convert necessary columns to numpy for speed
        idx_arr = df.index.to_numpy() # Not really needed if we interpret i as integer index
        close_arr = df['close'].to_numpy()
        high_arr = df['high'].to_numpy()
        low_arr = df['low'].to_numpy()
        mask_arr = entry_mask.to_numpy()
        
        # Risk params
        sl_mult = 1.0 - (strategy.stop_loss_pct / 100.0)
        tp_mult = 1.0 + (strategy.take_profit_pct / 100.0)
        max_bars = strategy.time_limit_bars
        
        while i < n - 1: # Need at least 1 bar to exit
            if mask_arr[i]:
                # === ENTRY ===
                entry_price = close_arr[i] # Assume enter on CLOSE of signal candle
                entry_idx = i
                
                # Determine Exit
                exit_pnl = 0.0
                
                # Look forward
                # Look forward
                highest_high = entry_price # Track highest price for trailing stop
                
                for j in range(i + 1, min(i + max_bars + 1, n)):
                    current_high = high_arr[j]
                    current_low = low_arr[j]
                    current_close = close_arr[j]
                    
                    # Update High Watermark
                    if current_high > highest_high:
                        highest_high = current_high
                        
                    # Check Exits
                    if strategy.use_trailing_stop:
                        # TRAILING STOP LOGIC
                        # Stop Price moves up
                        dynamic_stop_price = highest_high * sl_mult
                        
                        # Did we hit the trailing stop?
                        if current_low <= dynamic_stop_price:
                            # We exited at stop price
                            exit_price = dynamic_stop_price
                            # Correction: if gap down below stop, we exit at Open (not implemented here, assuming stop hit at price)
                            # Actually if Open is below stop, we exit at Open.
                            # For simplicity in vector sim:
                            
                            pct_change = (exit_price - entry_price) / entry_price * 100
                            exit_pnl = pct_change
                            i = j
                            break
                    
                    else:
                        # FIXED TP/SL LOGIC
                        # Did we hit SL?
                        if current_low <= entry_price * sl_mult:
                            exit_pnl = -strategy.stop_loss_pct
                            i = j 
                            break
                            
                        # Did we hit TP?
                        if current_high >= entry_price * tp_mult:
                            exit_pnl = strategy.take_profit_pct
                            i = j
                            break
                        
                    # Time limit
                    if j == i + max_bars:
                        # Close at market
                        exit_price = current_close
                        pct_change = (exit_price - entry_price) / entry_price * 100
                        exit_pnl = pct_change
                        i = j
                        break
                        
                    # End of Data (Close out)
                    if j == n - 1:
                        exit_price = current_close
                        pct_change = (exit_price - entry_price) / entry_price * 100
                        exit_pnl = pct_change
                        i = j
                        break
                
                trades.append(exit_pnl)
                # Next iteration starts at i + 1 (which creates gap/cooldown effectively)
            
            i += 1
            
        if not trades:
            return {'total_pnl': 0.0, 'num_trades': 0, 'win_rate': 0.0}
            
        total_pnl = sum(trades)
        wins = sum(1 for t in trades if t > 0)
        win_rate = (wins / len(trades)) * 100 if trades else 0
        
        return {
            'total_pnl': total_pnl,
            'num_trades': len(trades),
            'win_rate': win_rate,
            'trades': trades
        }
