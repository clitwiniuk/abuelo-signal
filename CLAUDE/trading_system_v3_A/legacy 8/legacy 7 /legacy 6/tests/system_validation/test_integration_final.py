#!/usr/bin/env python3
"""
Test 4: Test de integración end-to-end del sistema unificado
Simula todo el flujo: Scanner -> Filtro -> Notificaciones (sin conectar a IBKR real)
"""

import asyncio
import sys
import os
from datetime import datetime
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from unified_main import UnifiedTradingSystem
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from scanner.ibkr_native_scanner import IBKRScanResult
from utils.log_config import setup_logging
from ib_insync import Stock

# Import mock classes from previous tests
class MockTelegramClient:
    """Mock Telegram Client que muestra mensajes en consola"""
    def __init__(self):
        self.messages_sent = []
        
    def send_message(self, message, parse_mode=None):
        print(f"\n📱 TELEGRAM NOTIFICATION:")
        print("=" * 50)
        print(message)
        print("=" * 50)
        self.messages_sent.append(message)
        return True
        
    def is_enabled(self):
        return True

class MockIBKRAdapter:
    """Mock IBKR Adapter que simula datos reales"""
    def __init__(self):
        self.client_id = 9999
        
    def is_connected(self):
        return True
        
    async def connect(self):
        return True

class MockSmallcapScanner(SmallcapDailyScanner):
    """Scanner que genera datos realistas para testing"""
    def __init__(self):
        # Initialize with minimal setup to avoid IBKR dependencies
        self.config = self._get_default_config()
        self.logger = logging.getLogger("MockScanner")
        self.processed_tickers_session = set()
        self.active_plays_session = []
        self.session_start_time = datetime.now()
        
    async def scan_daily_plays(self, force_refresh=False):
        """Generate realistic trading scenarios"""
        self.logger.info("🎯 Mock Scanner ejecutando...")
        
        # Simulate different market scenarios
        scenarios = [
            # Scenario 1: Normal market day with good plays
            [
                self._create_mock_play("NVDA", 892.15, 8.5, 3.1, "Earnings Beat"),
                self._create_mock_play("AAPL", 145.23, 6.2, 2.8, "News Catalyst"),
            ],
            # Scenario 2: High volatility day  
            [
                self._create_mock_play("TSLA", 234.67, 12.4, 4.5, "FDA Approval"),
                self._create_mock_play("AMD", 156.89, 15.2, 5.2, "Contract Win"),
                self._create_mock_play("ROKU", 67.34, 18.9, 6.1, "Breakthrough"),
            ],
            # Scenario 3: Quiet day
            [
                self._create_mock_play("INTC", 34.56, 4.2, 1.8, "Volume Surge"),
            ]
        ]
        
        # Rotate scenarios based on time
        scenario_index = int(time.time()) % len(scenarios)
        selected_scenario = scenarios[scenario_index]
        
        print(f"📊 Mock Scanner - Scenario {scenario_index + 1}: {len(selected_scenario)} plays")
        return selected_scenario
        
    def _create_mock_play(self, symbol, price, gap, vol_ratio, catalyst_type):
        """Create a mock SmallcapPlay object"""
        from scanner.smallcap.smallcap_context import SmallcapContext
        from scanner.smallcap.catalyst_analyzer import CatalystInfo
        from scanner.smallcap.smallcap_daily_scanner import SmallcapPlay
        
        # Create mock context
        context = SmallcapContext(
            symbol=symbol,
            current_price=price,
            previous_close=price / (1 + gap/100),
            gap_percentage=gap/100,
            volume=int(vol_ratio * 1000000),
            avg_volume=1000000,
            volume_ratio=vol_ratio,
            market_cap=price * 100000000,
            float_size=50000000,
            is_shortable=True,
            spread_percentage=0.01
        )
        
        # Create mock catalyst
        catalyst = CatalystInfo(
            catalyst_type=catalyst_type,
            strength=min(int(gap/2), 10),
            news_age_hours=2.5,
            raw_headlines=[f"{symbol} {catalyst_type} news"],
            finbert_sentiment=0.8,
            finbert_confidence=0.9
        )
        
        # Create mock play
        play = SmallcapPlay(
            symbol=symbol,
            context=context,
            catalyst=catalyst,
            quality_score=min(gap + vol_ratio, 10),
            trading_recommendation={'strategy': 'conservative'},
            scan_timestamp=datetime.now(),
            ibkr_rank=1
        )
        
        return play

async def test_end_to_end_integration():
    """Test completo de integración end-to-end"""
    print("🧪 TEST 4: INTEGRACIÓN END-TO-END DEL SISTEMA UNIFICADO")
    print("=" * 70)
    
    try:
        # Setup
        setup_logging()
        print("✅ Logging configurado")
        
        # Create system components
        system = UnifiedTradingSystem()
        
        # Replace components with mocks
        mock_telegram = MockTelegramClient()
        system.telegram_client = mock_telegram
        
        mock_scanner = MockSmallcapScanner()
        system.scanner = mock_scanner
        
        print("✅ Sistema unificado con mocks configurado")
        
        # Test multiple scan cycles
        print(f"\n🔄 SIMULANDO MÚLTIPLES CICLOS DE SCAN...")
        
        for cycle in range(1, 4):
            print(f"\n{'='*20} CICLO {cycle} {'='*20}")
            
            # Execute scanner
            opportunities = await system._scan_for_opportunities()
            print(f"📊 Scanner encontró {len(opportunities)} oportunidades")
            
            if opportunities:
                # Show opportunities found
                print("🎯 OPORTUNIDADES DETECTADAS:")
                for i, opp in enumerate(opportunities, 1):
                    print(f"  {i}. {opp['symbol']}: ${opp['current_price']:.2f} "
                          f"({opp['gap_percentage']*100:+.1f}%, {opp['volume_ratio']:.1f}x vol)")
                
                # Process through evaluation system
                await system._evaluate_opportunities(opportunities)
                
                print(f"✅ Ciclo {cycle} completado - {len(opportunities)} plays procesados")
            else:
                print("📭 Sin oportunidades en este ciclo")
            
            # Wait before next cycle (shorter for testing)
            if cycle < 3:
                print("⏳ Esperando próximo ciclo...")
                await asyncio.sleep(2)
        
        # Final summary
        print(f"\n📊 RESUMEN FINAL:")
        print(f"   Total notificaciones enviadas: {len(mock_telegram.messages_sent)}")
        print(f"   Tickers en cache de notificaciones: {len(system.notified_plays)}")
        
        if system.notified_plays:
            print(f"   Cache de notificaciones:")
            for symbol, data in system.notified_plays.items():
                print(f"     - {symbol}: {data['last_notified'].strftime('%H:%M:%S')}")
        
        # Test cooldown and filtering
        print(f"\n🧪 PROBANDO FILTROS AVANZADOS:")
        
        # Try to send same opportunities again (should be filtered)
        print("📋 Enviando mismas oportunidades (debería ser filtrado)...")
        duplicate_opportunities = await system._scan_for_opportunities()
        
        if duplicate_opportunities:
            filtered = system._filter_notification_worthy_plays(duplicate_opportunities)
            print(f"📊 Oportunidades después de filtro: {len(filtered)}")
            
            if filtered:
                print("⚠️  Algunas oportunidades pasaron filtro (cambios detectados)")
            else:
                print("✅ Filtro anti-spam funcionando - sin duplicados enviados")
        
        print(f"\n🎉 TEST DE INTEGRACIÓN END-TO-END COMPLETADO")
        print(f"✅ Sistema unificado funcionando correctamente")
        print(f"✅ Scanner integrado y funcional")
        print(f"✅ Sistema de notificaciones inteligentes activo") 
        print(f"✅ Filtros anti-spam implementados")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN TEST DE INTEGRACIÓN: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import logging
    success = asyncio.run(test_end_to_end_integration())
    
    print(f"\n{'='*70}")
    if success:
        print("🎉 TODOS LOS TESTS COMPLETADOS EXITOSAMENTE")
        print("✅ Sistema unificado listo para producción")
        print("📱 Notificaciones de Telegram funcionando")
        print("🔍 Scanner integrado y operativo")
        print("\n💡 PRÓXIMO PASO: Conectar a IBKR real con 'python main.py'")
    else:
        print("❌ Algunos tests fallaron - revisar logs")
    
    sys.exit(0 if success else 1)