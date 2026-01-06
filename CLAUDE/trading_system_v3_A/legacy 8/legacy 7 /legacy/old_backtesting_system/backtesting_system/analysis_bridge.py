#!/usr/bin/env python3
import sys
import json
import os
import traceback

# Add the project root to sys.path to allow imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Import analysis modules
# Note: We'll need to adapt rule_extractor to be importable or call it here
try:
    from backtesting_system.rule_extractor_main.rule_extractor_stocks import run_rule_extractor_stocks
except ImportError:
    # Fallback or placeholder if import fails during development
    pass

def main():
    try:
        # Read input from stdin
        input_data = sys.stdin.read()
        if not input_data:
            raise ValueError("No input data received")
        
        request = json.loads(input_data)
        
        experiment_id = request.get('experimentId')
        analysis_type = request.get('type')
        parameters = request.get('parameters', {})
        trade_ids = request.get('tradeIds', [])
        
        result = {}
        
        if analysis_type == 'RULE_EXTRACTION':
            # TODO: Implement actual call to Rule Extractor
            # For now, return a mock result to verify the pipeline
            result = {
                "status": "success",
                "message": f"Rule Extraction executed for {len(trade_ids)} trades",
                "rules": [
                    {"condition": "rsi_14 < 30", "win_rate": 75.5, "trades": 12},
                    {"condition": "close > sma_200", "win_rate": 68.2, "trades": 25}
                ],
                "stats": {
                    "total_trades_analyzed": len(trade_ids),
                    "best_rule_win_rate": 75.5
                }
            }
            
        elif analysis_type == 'FORWARD_TEST':
            # Placeholder for Forward Test
            result = {
                "status": "success",
                "message": "Forward Test executed",
                "equity_curve": [1000, 1050, 1030, 1100]
            }
            
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
            
        # Print result as JSON to stdout
        print(json.dumps(result))
        
    except Exception as e:
        # Print error as JSON to stdout (or stderr)
        error_response = {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_response))
        sys.exit(1)

if __name__ == "__main__":
    main()
