import argparse
import sys
import os
import json
import shutil
import tempfile
import sqlite3
import pandas as pd
from datetime import datetime

# Ensure imports work regardless of CWD
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

try:
    from worker_gen.extract_training_data import extract_data
    from worker_gen.core.data_manager import DataManager
    from worker_gen.core.optimizer import Optimizer
    from worker_gen.core.code_writer import CodeWriter
    from worker_gen.core.robustness import RobustnessAnalyzer
except ImportError:
    # Fallback for when current_dir is the root of execution (less likely but possible)
    from extract_training_data import extract_data
    from core.data_manager import DataManager
    from core.optimizer import Optimizer
    from core.code_writer import CodeWriter
    from core.robustness import RobustnessAnalyzer

def get_db_path(base_dir=None):
    # Try current directory first
    if os.path.exists('trading_data.db'):
        return 'trading_data.db'
    # Then try parent directory (common when running from scripts/)
    if os.path.exists('../trading_data.db'):
        return '../trading_data.db'
    
    # Fallback to hardcoded path matching system config
    return '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db'

def fetch_labels(pattern_name, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
        SELECT symbol, date, start_bar, end_bar
        FROM pattern_labels
        WHERE pattern_name = ? COLLATE NOCASE
        ORDER BY date DESC
    """
    
    cursor.execute(query, (pattern_name,))
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def fetch_negative_labels(db_path, target_pattern, limit=50):
    """
    Fetches negative samples:
    1. explicit '_REVIEWED_' (no pattern)
    2. 'Hard Negatives': other patterns (e.g. if target is 'A+', fetch 'B-')
       BUT ensure we don't pick a day that ALSO has the target pattern (multi-label).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Logic:
    # Select labels where pattern IS NOT target AND IS NOT match for target
    # AND symbol/date NOT IN (subset where pattern == target)
    
    query = """
        SELECT DISTINCT symbol, date
        FROM pattern_labels t1
        WHERE 
            (pattern_name = '_REVIEWED_' AND is_match = 0)
            OR
            (pattern_name != ? AND pattern_name != '_REVIEWED_')
        AND NOT EXISTS (
            SELECT 1 FROM pattern_labels t2
            WHERE t2.symbol = t1.symbol 
            AND t2.date = t1.date 
            AND t2.pattern_name = ?
        )
        ORDER BY date DESC
        LIMIT ?
    """
    
    cursor.execute(query, (target_pattern, target_pattern, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # Return format compatible with loop: (symbol, date, 0, 0)
    # We default bars to 0,0 since we extract whole day anyway
    return [(r[0], r[1], 0, 0) for r in rows]

def main():
    parser = argparse.ArgumentParser(description='Generate Worker from Pattern Labels')
    parser.add_argument('--pattern', required=True, help='Name of the pattern to learn from')
    parser.add_argument('--iterations', type=int, default=500, help='Number of total evaluations (converted to generations)')
    parser.add_argument('--trailing', action='store_true', help='Use Trailing Stop for exits instead of Fixed TP')
    parser.add_argument('--smart', action='store_true', help='Use Smart Optimization (Early Stopping + Stability Filter)')
    parser.add_argument('--db', help='Database path (optional)')
    
    args = parser.parse_args()
    
    response = {
        "success": False,
        "pattern": args.pattern,
        "samples_count": 0,
        "stats": {},
        "code": None,
        "error": None
    }
    
    try:
        # Redirect stdout to stderr for intermediate logs to keep stdout clean for JSON
        original_stdout = sys.stdout
        sys.stdout = sys.stderr
        
        try:
            # 1. Setup paths
            db_path = args.db if args.db else get_db_path()
            if not os.path.exists(db_path):
                raise FileNotFoundError(f"Database not found at {db_path}")
                
            # 2. Create temp directory for training data
            with tempfile.TemporaryDirectory() as temp_dir:
                # 3. Fetch labels
                labels = fetch_labels(args.pattern, db_path)
                response["samples_count"] = len(labels)
                
                if len(labels) < 5:
                    # Need a minimum amount of data to be useful
                    raise ValueError(f"Insufficient data. Found {len(labels)} samples, need at least 5 to train.")
                    
                # 4. Extract data for each label
                print(f"Extracting sample data to {temp_dir}...", file=sys.stderr)
                valid_samples = 0
                for symbol, date, start_bar, end_bar in labels:
                    # We extract the Full Day for context, the optimizer treats the whole file as a "day" to trade
                    # Ideally we might clip to the specific time window, but for now full day context is better for indicators
                    success = extract_data(symbol, date, temp_dir, db_path=db_path)
                    if success:
                        valid_samples += 1
                
                if valid_samples == 0:
                    raise ValueError("Failed to extract any valid OHLC data for the labels.")

                # 5. Extract Negative Samples (Background Noise + Hard Negatives)
                print(f"Extracting negative samples...", file=sys.stderr)
                # Pass target pattern to exclude it from negatives
                neg_labels = fetch_negative_labels(db_path, args.pattern, limit=50) 
                neg_samples = 0
                
                for symbol, date, start_bar, end_bar in neg_labels:
                    # Prefix filename with NEG_ to identify in Optimizer
                    # We need to modify extract_data or manually rename after extraction? 
                    # extract_data saves as {symbol}_{date}.csv
                    # Let's extract then rename
                    success = extract_data(symbol, date, temp_dir, db_path=db_path)
                    if success:
                        original_path = os.path.join(temp_dir, f"{symbol}_{date}.csv")
                        new_path = os.path.join(temp_dir, f"NEG_{symbol}_{date}.csv")
                        if os.path.exists(original_path):
                            os.rename(original_path, new_path)
                            neg_samples += 1
                
                response["negative_samples_count"] = neg_samples

                # 6. Load Data
                print(f"Loading data into optimizer (Pos: {valid_samples}, Neg: {neg_samples})...", file=sys.stderr)
                dm = DataManager(temp_dir)
                dm.load_all()
                
                if not dm.get_data():
                    raise ValueError("No valid data loaded after extraction.")

                # 6. Optimize
                print(f"Running genetic optimization ({args.iterations} iterations)...", file=sys.stderr)
                opt = Optimizer(dm)
                
                best_genome, robustness_stats = opt.optimize(iterations=args.iterations, 
                                                           use_trailing_stop=args.trailing,
                                                           smart_optimize=args.smart)
                
                if not best_genome:
                    raise ValueError("Optimization failed to find a profitable strategy.")
                    
                # 7. Generate Code
                writer = CodeWriter()
                class_name = args.pattern.replace(' ', '').replace('-', '').replace('_', '') + "WorkerLogic"
                generated_code = writer.generate(best_genome, class_name)
                rules_summary = writer.get_rules_description(best_genome)

                # 8. Run Walk-Forward Validation
                print("Running Walk-Forward Validation...", file=sys.stderr)
                wf_stats = RobustnessAnalyzer.run_walk_forward_validation(best_genome, dm.get_data())
                
                # 9. Compile Response
                response["success"] = True

                # Extract and serialize extracted_rules BEFORE adding to stats
                extracted_rules_data = robustness_stats.get('extracted_rules', {})
                response["extracted_rules"] = {
                    "single_rules": [str(r) for r in extracted_rules_data.get('single_rules', [])[:10]],
                    "combo_rules": [str(r) for r in extracted_rules_data.get('combo_rules', [])[:5]],
                    "negative_patterns": extracted_rules_data.get('negative_patterns', []) if isinstance(extracted_rules_data.get('negative_patterns', []), list) else []
                }

                # Remove extracted_rules from robustness_stats (contains non-serializable objects)
                robustness_stats_clean = {k: v for k, v in robustness_stats.items() if k != 'extracted_rules'}

                # Merge stats from optimizer (contains blind_pnl, consistency, etc.)
                response["stats"] = robustness_stats_clean

                # Add/Ensure standard fields
                response["stats"]["fitness"] = best_genome.fitness

                # Ensure robustness_status is set (optimizer should already provide this)
                if "robustness_status" not in response["stats"]:
                    response["stats"]["robustness_status"] = "unknown"

                # Placeholder if not provided by optimizer directly
                if "win_rate" not in response["stats"]:
                     response["stats"]["win_rate"] = 0
                if "profit_factor" not in response["stats"]:
                     response["stats"]["profit_factor"] = 0

                response["code"] = generated_code
                response["rules_summary"] = writer.get_rules_description(best_genome)
                response["walk_forward_stats"] = wf_stats

        finally:
            # Restore stdout for JSON output
            sys.stdout = original_stdout
            
    except Exception as e:
        sys.stdout = sys.__stdout__ # Ensure we can print
        response["error"] = str(e)
        # print error to stderr for debugging
        print(f"Error: {e}", file=sys.stderr)
        
    # Create valid JSON output
    print(json.dumps(response, indent=2))

if __name__ == "__main__":
    main()
