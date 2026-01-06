#!/usr/bin/env python3
"""
Script to add strategy_name parameter to all Signal creations
"""

import re
import os
from pathlib import Path

def fix_strategy_file(file_path, strategy_name):
    """Fix a single strategy file by adding strategy_name to Signal creations"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match Signal constructor calls
    # Look for: return Signal(... without strategy_name=
    signal_pattern = r'(return Signal\(\s*(?:[^)]*?,\s*)*timestamp=[^,)]+)(,?\s*metadata=)'
    
    # Replace with strategy_name added before metadata
    replacement = f'\\1,\n            strategy_name="{strategy_name}"\\2'
    
    content = re.sub(signal_pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    # Also handle cases where there's no metadata parameter
    signal_pattern_no_metadata = r'(return Signal\(\s*(?:[^)]*?,\s*)*timestamp=[^,)]+)(\s*\))'
    replacement_no_metadata = f'\\1,\n            strategy_name="{strategy_name}"\\2'
    
    content = re.sub(signal_pattern_no_metadata, replacement_no_metadata, content, flags=re.MULTILINE | re.DOTALL)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✅ Fixed {file_path} - added strategy_name='{strategy_name}'")
        return True
    else:
        print(f"⚠️  No changes needed in {file_path}")
        return False

def main():
    """Fix all strategy files"""
    
    strategies_dir = Path(__file__).parent / 'strategies'
    
    # Map of file names to strategy names
    strategy_mapping = {
        'base.py': 'Base_Strategy',
        'gap_go_strategy.py': 'Gap_Go',
        'macdv_strategy.py': 'MACDV_Smallcaps',
        'optimized_gap_go_strategy.py': 'Optimized_Gap_Go',
        'pmh_breakout_strategy.py': 'PMH_Breakout',
        'volume_breakout_strategy.py': 'Volume_Breakout',  # Already fixed manually
        'volume_momentum_strategy.py': 'Volume_Momentum',
        'vwap_strategy.py': 'VWAP_Strategy'
    }
    
    fixed_count = 0
    
    print("🔧 FIXING STRATEGY_NAME IN ALL STRATEGY FILES")
    print("=" * 60)
    
    for filename, strategy_name in strategy_mapping.items():
        file_path = strategies_dir / filename
        
        if file_path.exists():
            if fix_strategy_file(file_path, strategy_name):
                fixed_count += 1
        else:
            print(f"❌ File not found: {file_path}")
    
    print("\n" + "=" * 60)
    print(f"🎯 SUMMARY: Fixed {fixed_count} strategy files")
    print("✅ All strategy Signal creations now include strategy_name parameter")

if __name__ == "__main__":
    main()