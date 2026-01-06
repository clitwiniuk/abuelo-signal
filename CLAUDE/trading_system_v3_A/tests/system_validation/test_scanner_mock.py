#!/usr/bin/env python3
"""
Test 2: Probar funcionalidad del scanner con datos simulados
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from scanner.ibkr_native_scanner import IBKRScanResult
from utils.log_config import setup_logging
from ib_insync import Contract, Stock

class MockIBKRAdapter:
    """Mock IBKR Adapter para testing"""
    def __init__(self):
        self.client_id = 9999
        self.is_connected_flag = False
        
    def is_connected(self):
        return self.is_connected_flag
        
    async def connect(self):
        self.is_connected_flag = True
        return True
        
    async def disconnect(self):
        self.is_connected_flag = False

class MockIBKRNativeScanner:
    """Mock Scanner que genera datos de prueba"""
    def __init__(self, ibkr_adapter=None):
        self.ibkr_adapter = ibkr_adapter
        
    async def scan_daily_plays(self, max_results=10):
        """Generar datos de prueba simulando plays reales"""
        mock_results = [
            IBKRScanResult(
                symbol="NVDA",
                contract=Stock("NVDA", "SMART", "USD"),
                rank=1,
                distance="12.5%",
                benchmark="Gap Up",
                projection="Bullish",
                legs="",
                current_price=892.15,
                gap_percentage=12.5,
                volume=2500000,
                avg_volume=800000,
                market_cap=2200000000
            ),
            IBKRScanResult(
                symbol="AAPL", 
                contract=Stock("AAPL", "SMART", "USD"),
                rank=2,
                distance="8.4%",
                benchmark="Volume Surge",
                projection="Neutral",
                legs="",
                current_price=145.23,
                gap_percentage=8.4,
                volume=1800000,
                avg_volume=600000,
                market_cap=2500000000
            ),
            IBKRScanResult(
                symbol="TSLA",
                contract=Stock("TSLA", "SMART", "USD"),
                rank=3,
                distance="6.2%",
                benchmark="Gap Down",
                projection="Bearish",
                legs="",
                current_price=234.67, 
                gap_percentage=-6.2,
                volume=3200000,
                avg_volume=900000,
                market_cap=750000000
            )
        ]
        
        print(f"🎯 Mock Scanner generó {len(mock_results)} resultados")
        return mock_results

async def test_scanner_functionality():
    """Test del scanner con datos simulados"""
    print("🧪 TEST 2: FUNCIONALIDAD DEL SCANNER")
    print("=" * 50)
    
    try:
        # Setup logging
        setup_logging()
        print("✅ Logging configurado")
        
        # Create mock IBKR adapter
        mock_ibkr = MockIBKRAdapter()
        await mock_ibkr.connect()
        print("✅ Mock IBKR Adapter conectado")
        
        # Patch the scanner to use mock
        scanner = SmallcapDailyScanner(ibkr_adapter=mock_ibkr)
        
        # Replace the IBKR scanner with our mock
        scanner.ibkr_scanner = MockIBKRNativeScanner(mock_ibkr)
        print("✅ Scanner con Mock IBKR inicializado")
        
        # Test scan operation
        print("\n🔍 Ejecutando scan de prueba...")
        plays = await scanner.scan_daily_plays(force_refresh=True)
        
        print(f"\n📊 RESULTADOS DEL SCAN:")
        print(f"   Total plays encontrados: {len(plays)}")
        
        if plays:
            print("\n📈 PLAYS DETECTADOS:")
            for i, play in enumerate(plays[:3], 1):  # Show first 3
                print(f"{i}. {play.symbol}")
                print(f"   Precio: ${play.context.current_price:.2f}")
                print(f"   Gap: {play.context.gap_percentage:+.1f}%")
                print(f"   Quality Score: {play.quality_score:.1f}")
                print(f"   Catalyst: {play.catalyst.catalyst_type}")
                print(f"   Strength: {play.catalyst.strength}")
                print()
        else:
            print("⚠️  No se encontraron plays (puede ser por filtros de calidad)")
            
        # Test session stats
        stats = scanner.get_session_stats()
        print(f"📊 ESTADÍSTICAS DE SESIÓN:")
        print(f"   Tickers procesados: {stats['processed_tickers']}")
        print(f"   Plays activos: {stats['active_plays_count']}")
        print(f"   Duración de sesión: {stats['session_duration']}")
        
        # Test formatted output
        if plays:
            formatted_output = scanner.get_formatted_output(plays[:2])
            print(f"\n📝 FORMATO DE OUTPUT (muestra):")
            print(formatted_output[:500] + "..." if len(formatted_output) > 500 else formatted_output)
        
        print("\n🎉 SCANNER TEST COMPLETADO EXITOSAMENTE")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN TEST 2: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            await mock_ibkr.disconnect()
            print("✅ Mock IBKR desconectado")
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_scanner_functionality())
    sys.exit(0 if success else 1)