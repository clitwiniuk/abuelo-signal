import os
from .strategy_dna import StrategyGenome

WORKER_TEMPLATE = """
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.workers.base_worker_logic import BaseWorkerLogic

class {class_name}(BaseWorkerLogic):
    \"\"\"
    Auto-Generated Worker by WorkerGen AI.
    Strategy Score: {fitness:.2f}
    \"\"\"
    
    def __init__(self, worker_name, config, execution_engine, risk_manager, event_queue):
        super().__init__(worker_name, config, execution_engine, risk_manager, event_queue)
        self.logger = logging.getLogger(f"Worker.{{worker_name}}")
        
        # Optimized Parameters
        self.stop_loss_pct = {sl}
        self.take_profit_pct = {tp}

        self.time_limit_bars = {time_limit}
        self.use_trailing_stop = {trailing}
        
        # Time Window (Minutes from Open 9:30)
        self.entry_window_start = {win_start}
        self.entry_window_end = {win_end}

    async def should_enter(self, opportunity):
        \"\"\"
        Evaluates entry based on optimized genetic conditions.
        \"\"\"
        symbol = opportunity['symbol']
        
        # 1. Get History (Enough for EMA 200)
        # We request 300 bars to be safe for indicators
        bars = await self.execution_engine.get_history(symbol, 300, '1 min')
        
        if not bars or len(bars) < 200:
            self.logger.warning(f"{{symbol}}: Insufficient history {{len(bars)}}")
            return False
            
        # 2. Prepare DataFrame
        df = pd.DataFrame(bars)
        # Ensure standard columns (assuming bar objects or dicts)
        # If bars are objects, convert:
        if hasattr(bars[0], 'close'):
             df = pd.DataFrame([vars(b) for b in bars])
             
        # Normalize columns if needed
        # (Assuming standard names from system: open, high, low, close, volume)
        
        # 3. Check Time Window
        if 'timestamp' in df.columns:
            last_time = pd.to_datetime(df.iloc[-1]['timestamp'])
            # Calc minutes from open (9:30 = 570)
            # Handle potential datetime object or string
            minutes_from_open = (last_time.hour * 60 + last_time.minute) - 570
            
            if not (self.entry_window_start <= minutes_from_open <= self.entry_window_end):
                # Outside allowed window
                return False
        
        # 3. Calculate Indicators
        close = df['close']
        
        # EMAs
        df['ema_9'] = close.ewm(span=9, adjust=False).mean()
        df['ema_20'] = close.ewm(span=20, adjust=False).mean()
        df['ema_50'] = close.ewm(span=50, adjust=False).mean()
        df['ema_200'] = close.ewm(span=200, adjust=False).mean()
        
        # RSI 14
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # VWAP (Intraday approx)
        df['cum_vol'] = df['volume'].cumsum()
        df['cum_pv'] = (df['close'] * df['volume']).cumsum() # Approx
        df['vwap'] = df['cum_pv'] / df['cum_vol']
        
        # Relative Volume
        df['vol_sma_20'] = df['volume'].rolling(window=20).mean()
        df['rvol'] = df['volume'] / df['vol_sma_20']
        
        # Distance to EMA9
        df['dist_ema_9'] = (close - df['ema_9']) / df['ema_9'] * 100
        
        # 4. Evaluate Last Bar
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- GENERATED CONDITIONS ---
        # Logic: {logic_description}
        
        {logic_code}
            
        self.logger.info(f"✅ {{symbol}}: Strategy Entry Triggered!")
        return True

    async def should_exit(self, position, current_bar):
        \"\"\"
        Simple SL/TP/Time exit logic.
        \"\"\"
        # This is handled by StopManager usually, but if custom logic needed:
        # For V3, we rely on the stop_manager primarily, but can force exit here.
        # We will leave this flexible or delegate.
        return False
"""

class CodeWriter:
    """Generates Python code from StrategyGenome."""
    
    def generate(self, genome: StrategyGenome, class_name: str) -> str:
        # Sanitize class_name to be a valid Python identifier
        # 1. Replace invalid chars with empty string or underscore
        import re
        # Remove anything that isn't alphanumeric or underscore
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '', class_name)
        # Ensure it starts with a letter
        if not clean_name or not clean_name[0].isalpha():
            clean_name = "GenWorker" + clean_name
            
        class_name = clean_name
        
        # Translate conditions to Python code
        # Example condition: Condition(left='rsi_14', operator='<', right=30)
        # Becomes: if not (current['rsi_14'] < 30): return False
        
        logic_lines = []
        descriptions = []
        
        for cond in genome.entry_conditions:
            left_expr = f"current['{cond.left}']"
            
            if isinstance(cond.right, str):
                right_expr = f"current['{cond.right}']"
            else:
                right_expr = str(cond.right)
                
            python_op = cond.operator # >, <, >=, <= work as is
            
            line = f"if not ({left_expr} {python_op} {right_expr}):"
            descriptions.append(str(cond))
            
            logic_lines.append(line)
            # Add logging or return false
            logic_lines.append(f"    # Fail: {cond}")
            logic_lines.append(f"    return False")
            
        logic_block = "\n        ".join(logic_lines)
        logic_desc = " AND ".join(descriptions)
        
        code = WORKER_TEMPLATE.format(
            class_name=class_name,
            fitness=genome.fitness,
            sl=genome.stop_loss_pct,
            tp=genome.take_profit_pct,
            time_limit=genome.time_limit_bars,
            trailing="{}" .format(genome.use_trailing_stop),
            win_start=genome.entry_window_start,
            win_end=genome.entry_window_end,
            logic_description=logic_desc,
            logic_code=logic_block
        )
        
        return code
    
    def get_rules_description(self, genome: StrategyGenome) -> list[str]:
        """Generates a human-readable list of rules."""
        rules = []
        
        for cond in genome.entry_conditions:
            # Map technical names to human readable
            left = cond.left.replace('_', ' ').upper()
            right = str(cond.right).replace('_', ' ').upper()
            
            op_map = {
                '>': 'greater than',
                '<': 'less than',
                '>=': 'greater than or equal to', 
                '<=': 'less than or equal to',
                '==': 'equal to'
            }
            op = op_map.get(cond.operator, cond.operator)
            
            rules.append(f"{left} must be {op} {right}")
            
        return rules

    def save(self, code: str, filename: str):
        with open(filename, 'w') as f:
            f.write(code)
        print(f"✅ Code saved to {filename}")
