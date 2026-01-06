#!/usr/bin/env python3
"""
Quick test of corrected screener with small sample
"""

import os
import sys
import time
sys.path.append(os.path.join(os.path.dirname(__file__)))

from finviz_screener import FinvizSmallcapsScreener

def test_corrected_screener():
    """Test the corrected screener with a limited set of known smallcaps"""
    
    # Test tickers that might have high short float
    test_tickers = [
        'CARV', 'SAVA', 'MBOT', 'AMC', 'CRBP', 'TNXP', 'GALT', 'NVFY',
        'AVXL', 'BDTX', 'BLNK', 'SPCE', 'NRXP', 'INDO', 'KALA', 'BYRN'
    ]
    
    print("🔍 TESTING CORRECTED SCREENER")
    print("=" * 50)
    print(f"📊 Testing {len(test_tickers)} known smallcaps")
    print("🎯 Criteria: price $1-$5, short_float >35%, RSI <45, volume >500K, mcap <500M")
    print()
    
    # Create screener without Polygon (faster testing)
    screener = FinvizSmallcapsScreener(polygon_api_key=None)
    
    print("🔍 MANUAL FILTERING RESULTS:")
    print("-" * 50)
    
    candidates = []
    
    for i, ticker in enumerate(test_tickers, 1):
        print(f"[{i:2}/{len(test_tickers)}] Testing {ticker}...", end=" ")
        
        data = screener.get_finviz_ticker_data(ticker)
        
        if data is None:
            print("❌ No data")
            continue
            
        # Apply manual filters
        price = data.get('price', 0)
        market_cap = data.get('market_cap', 0)
        rsi = data.get('rsi', 100)
        short_float = data.get('short_float', 0)
        volume = data.get('avg_volume', 0)
        
        # Checks
        price_ok = 1.0 <= price <= 5.0 if price else False
        mcap_ok = market_cap <= 500e6 if market_cap else False
        rsi_ok = rsi <= 45 if rsi else False
        short_ok = short_float >= 35 if short_float else False
        volume_ok = volume >= 500000 if volume else False
        
        # Status
        status = "✅" if all([price_ok, mcap_ok, rsi_ok, short_ok, volume_ok]) else "❌"
        
        # Safe formatting
        price_str = f"${price:.2f}" if price else "$N/A"
        mcap_str = f"{market_cap/1e6:.0f}M" if market_cap else "N/A"
        rsi_str = f"{rsi:.1f}" if rsi else "N/A"
        sf_str = f"{short_float:.1f}%" if short_float else "N/A"
        vol_str = f"{volume/1000:.0f}K" if volume else "N/A"
        
        print(f"\n   {status} {ticker:<6} | {price_str:<7} | MCap: {mcap_str:<6} | RSI: {rsi_str:<6} | SF: {sf_str:<7} | Vol: {vol_str:<6}")
        
        if all([price_ok, mcap_ok, rsi_ok, short_ok, volume_ok]):
            candidates.append(data)
            
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n🎯 RESULTS:")
    print(f"✅ Candidates found: {len(candidates)}")
    
    if candidates:
        print("\n🏆 SQUEEZE CANDIDATES:")
        for candidate in candidates:
            price = candidate.get('price', 0)
            rsi = candidate.get('rsi', 0)
            short_float = candidate.get('short_float', 0)
            volume = candidate.get('avg_volume', 0)
            print(f"   🎯 {candidate['ticker']} | ${price:.2f} | RSI: {rsi:.1f} | SF: {short_float:.1f}% | Vol: {volume/1000:.0f}K")
    else:
        print("\n💡 No candidates found with >35% short float")
        print("   Consider lowering short_float criteria (e.g., >20% or >15%)")
        
        # Show top short float candidates
        print("\n📊 TOP SHORT FLOAT CANDIDATES (any %):")
        all_data = []
        for ticker in test_tickers:
            data = screener.get_finviz_ticker_data(ticker)
            if data and data.get('short_float', 0) > 0:
                all_data.append(data)
                time.sleep(0.3)
        
        # Sort by short float
        all_data.sort(key=lambda x: x.get('short_float', 0), reverse=True)
        
        for data in all_data[:5]:
            price = data.get('price', 0)
            rsi = data.get('rsi', 0)
            short_float = data.get('short_float', 0)
            volume = data.get('avg_volume', 0)
            print(f"   📊 {data['ticker']} | ${price:.2f} | RSI: {rsi:.1f} | SF: {short_float:.1f}% | Vol: {volume/1000:.0f}K")

if __name__ == "__main__":
    test_corrected_screener()