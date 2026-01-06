#!/usr/bin/env python3
"""
Test script for strategy code analyzer
"""

from strategy_code_analyzer import StrategyCodeAnalyzer

def test_analyzer():
    print("🔬 TESTING STRATEGY CODE ANALYZER")
    print("=" * 60)
    
    analyzer = StrategyCodeAnalyzer()
    
    # Analizar MACDVStrategy
    print("\n📊 Analizando MACDVStrategy...")
    analysis = analyzer.analyze_strategy_code('MACDVStrategy')
    
    if 'error' in analysis:
        print(f"❌ Error: {analysis['error']}")
    else:
        analyzer.print_analysis_report(analysis)

if __name__ == "__main__":
    test_analyzer()