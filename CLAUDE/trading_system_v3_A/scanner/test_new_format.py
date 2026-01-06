# scanner/test_new_format.py
"""
Test the new ProRealTime format parser
"""

from daily_plays_filter import TickerData

# Test data in new format
NEW_FORMAT_DATA = '''
"Ticker"    "Nombre"    "%Var"    "Var"    "Último"    "Inserción"    "Volumen"
"ATNF"    "180 LIFE SCIENCES"    "+206,59%"    "+6,90"    "10,24(c)"    "07:00:33"    "225M"
"AAL"    "AMERICAN AIRLINES GROUP INC."    "+12,09%"    "+1,40"    "12,98(c)"    "07:00:33"    "115M"
"ORIS"    "ORIENTAL RISE HOLDINGS"    "+12,34%"    "+0,0134"    "0,1220(c)"    "07:00:33"    "102M"
"ONDS"    "ONDAS HOLDINGS INC."    "+25,07%"    "+0,86"    "4,29(c)"    "07:00:33"    "73M"
"JBLU"    "JETBLUE AIRWAYS"    "+12,18%"    "+0,52"    "4,79(c)"    "07:00:33"    "34,7M"
'''

def test_new_format_parser():
    """Test the parser with the new format"""
    print("🧪 Testing New ProRealTime Format Parser")
    print("=" * 50)
    
    lines = NEW_FORMAT_DATA.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('"Ticker"'):  # Skip header
            continue
            
        print(f"📋 Parsing: {line[:60]}...")
        
        ticker_data = TickerData.from_prt_line(line)
        
        if ticker_data:
            print(f"   ✅ {ticker_data.ticker}: {ticker_data.var_pct:+.2f}% @ ${ticker_data.last_price} Vol:{ticker_data.volume}")
        else:
            print(f"   ❌ Failed to parse")
        print()
    
    print("=" * 50)
    print("✅ New format parser test completed!")

if __name__ == "__main__":
    test_new_format_parser()