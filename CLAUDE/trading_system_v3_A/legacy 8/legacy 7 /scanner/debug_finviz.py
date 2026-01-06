# scanner/debug_finviz.py
"""
Debug script to understand Finviz data format
"""

try:
    from finvizfinance.quote import finvizfinance
    FINVIZ_AVAILABLE = True
except ImportError:
    FINVIZ_AVAILABLE = False
    print("❌ finvizfinance not available - install with: pip install finvizfinance")

def debug_finviz_format():
    """Debug the exact format returned by finvizfinance"""
    if not FINVIZ_AVAILABLE:
        return
    
    # Test with a well-known stock
    ticker = "AAPL"
    print(f"🔍 Debugging Finviz data format for {ticker}")
    print("=" * 50)
    
    try:
        # Initialize Finviz for this ticker
        stock = finvizfinance(ticker)
        
        # Get news data
        news_data = stock.ticker_news()
        
        print(f"📰 Type of news_data: {type(news_data)}")
        print(f"📰 news_data is None: {news_data is None}")
        
        if news_data is not None:
            # Check if it's a DataFrame
            if hasattr(news_data, 'empty'):
                print(f"📰 Is DataFrame: True")
                print(f"📰 Is empty: {news_data.empty}")
                print(f"📰 Shape: {news_data.shape}")
                print(f"📰 Columns: {list(news_data.columns) if hasattr(news_data, 'columns') else 'No columns'}")
                
                if not news_data.empty:
                    print(f"📰 First few rows:")
                    print(news_data.head(3))
                    print()
                    
                    print(f"📰 First row data:")
                    first_row = news_data.iloc[0]
                    for i, value in enumerate(first_row):
                        print(f"   Column {i}: {value}")
                    print()
            
            elif isinstance(news_data, list):
                print(f"📰 Is list: True")
                print(f"📰 Length: {len(news_data)}")
                if news_data:
                    print(f"📰 First item: {news_data[0]}")
                    print(f"📰 Type of first item: {type(news_data[0])}")
            
            else:
                print(f"📰 Unknown format: {type(news_data)}")
                print(f"📰 Content: {news_data}")
        
        print("=" * 50)
        print("✅ Debug completed")
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_finviz_format()