#!/usr/bin/env python3
"""
Debug Finviz Fields
==================

Script para ver qué campos exactos devuelve Finviz para un ticker
"""

try:
    from finvizfinance.quote import finvizfinance
    FINVIZ_AVAILABLE = True
except ImportError:
    print("❌ finvizfinance not installed")
    FINVIZ_AVAILABLE = False


def debug_ticker_fields(ticker: str):
    """Debug los campos de un ticker específico"""
    
    if not FINVIZ_AVAILABLE:
        return
    
    try:
        stock = finvizfinance(ticker)
        fundamentals = stock.ticker_fundament()
        
        print(f"🔍 DEBUGGING FIELDS FOR {ticker}")
        print("=" * 50)
        
        if fundamentals:
            print("📊 All available fields:")
            for key, value in fundamentals.items():
                print(f"   '{key}': '{value}'")
                
            print(f"\n🎯 KEY FIELDS:")
            print(f"   Price: {fundamentals.get('Price', 'N/A')}")
            print(f"   Short Float: {fundamentals.get('Short Float', 'N/A')}")
            print(f"   Short Ratio: {fundamentals.get('Short Ratio', 'N/A')}")
            print(f"   Short Interest: {fundamentals.get('Short Interest', 'N/A')}")
            print(f"   RSI (14): {fundamentals.get('RSI (14)', 'N/A')}")
            print(f"   Avg Volume: {fundamentals.get('Avg Volume', 'N/A')}")
            print(f"   Market Cap: {fundamentals.get('Market Cap', 'N/A')}")
        else:
            print("❌ No fundamentals data returned")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    # Test con tickers que sabemos que tienen short interest
    test_tickers = ['GME', 'AMC', 'SAVA', 'MBOT']
    
    for ticker in test_tickers:
        debug_ticker_fields(ticker)
        print("\n" + "-"*50 + "\n")


if __name__ == "__main__":
    main()