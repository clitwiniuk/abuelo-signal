#!/usr/bin/env python3
"""
Test script to diagnose FINVIZ AttributeError for CRCG
"""

import sys
import traceback

try:
    from finvizfinance.quote import finvizfinance
    print("✅ finvizfinance imported successfully")
except ImportError as e:
    print(f"❌ Cannot import finvizfinance: {e}")
    sys.exit(1)

def test_finviz_crcg():
    """Test Finviz with CRCG to reproduce the error"""
    symbol = 'CRCG'

    print(f"\n{'='*60}")
    print(f"Testing Finviz with symbol: {symbol}")
    print(f"{'='*60}\n")

    try:
        print("Step 1: Creating finvizfinance object...")
        stock = finvizfinance(symbol)
        print(f"✅ Object created: {type(stock)}")
        print(f"   Object attributes: {dir(stock)}")

        print("\nStep 2: Checking if ticker_news method exists...")
        if hasattr(stock, 'ticker_news'):
            print("✅ ticker_news method exists")
        else:
            print("❌ ticker_news method NOT found!")
            print(f"   Available methods: {[m for m in dir(stock) if not m.startswith('_')]}")
            return

        print("\nStep 3: Calling ticker_news()...")
        news_data = stock.ticker_news()
        print(f"✅ ticker_news() returned: {type(news_data)}")

        print("\nStep 4: Analyzing returned data...")
        if news_data is None:
            print("⚠️  news_data is None")
            return

        print(f"   Type: {type(news_data)}")
        print(f"   Attributes: {dir(news_data)}")

        # Check for DataFrame attributes
        print("\nStep 5: Checking DataFrame attributes...")
        if hasattr(news_data, 'empty'):
            print(f"✅ Has 'empty' attribute: {news_data.empty}")
        else:
            print("❌ NO 'empty' attribute!")

        if hasattr(news_data, 'shape'):
            print(f"✅ Has 'shape' attribute: {news_data.shape}")
        else:
            print("❌ NO 'shape' attribute!")

        if hasattr(news_data, 'iterrows'):
            print("✅ Has 'iterrows' method")
        else:
            print("❌ NO 'iterrows' method!")

        if hasattr(news_data, 'columns'):
            print(f"✅ Has 'columns' attribute: {list(news_data.columns)}")
        else:
            print("❌ NO 'columns' attribute!")

        # Try to access data
        print("\nStep 6: Attempting to iterate rows...")
        try:
            if hasattr(news_data, 'empty') and not news_data.empty:
                print(f"   DataFrame has {len(news_data)} rows")
                for idx, row in news_data.head(3).iterrows():
                    print(f"\n   Row {idx}:")
                    print(f"      Type: {type(row)}")
                    if hasattr(row, 'keys'):
                        print(f"      Keys: {list(row.keys())}")
                    if 'Title' in row:
                        print(f"      Title: {row['Title']}")
                    if 'Date' in row:
                        print(f"      Date: {row['Date']}")
            else:
                print("   DataFrame is empty or doesn't have 'empty' attribute")
        except AttributeError as e:
            print(f"   ❌ AttributeError during iteration: {e}")
            traceback.print_exc()
        except Exception as e:
            print(f"   ❌ Error during iteration: {type(e).__name__}: {e}")
            traceback.print_exc()

        print("\n✅ Test completed successfully!")

    except AttributeError as e:
        print(f"\n❌ AttributeError caught!")
        print(f"   Error: {e}")
        print(f"\n   Full traceback:")
        traceback.print_exc()

        print(f"\n   Analyzing where error occurred:")
        print(f"   - Error type: {type(e).__name__}")
        print(f"   - Error message: {str(e)}")

    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}")
        print(f"   Error: {e}")
        print(f"\n   Full traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    test_finviz_crcg()

    # Also test with a known good symbol
    print("\n\n" + "="*60)
    print("Testing with a known good symbol (AAPL) for comparison")
    print("="*60)

    symbol = 'AAPL'
    try:
        stock = finvizfinance(symbol)
        news_data = stock.ticker_news()
        print(f"✅ AAPL test successful: {type(news_data)}")
        if hasattr(news_data, 'empty'):
            print(f"   Empty: {news_data.empty}")
            if not news_data.empty:
                print(f"   Rows: {len(news_data)}")
    except Exception as e:
        print(f"❌ AAPL test failed: {type(e).__name__}: {e}")
