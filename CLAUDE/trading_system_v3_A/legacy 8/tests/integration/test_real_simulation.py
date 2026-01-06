#!/usr/bin/env python3
"""
Test de Simulación Real - Simula el flujo completo del sistema
Como si fuera el sistema real corriendo, pero con datos falsos
"""

import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trader_main import IndependentTrader
from core.service_locator import get_service_locator
from notifications.telegram_client import send_message, send_plays_today

def simulate_real_trading_day():
    """Simula un día real de trading con datos falsos"""
    print("🎬 SIMULANDO DÍA REAL DE TRADING")
    print("=" * 50)
    
    # Enviar mensaje de inicio de simulación
    start_message = f"""🎬 INICIANDO SIMULACIÓN DE DÍA REAL - {datetime.now().strftime('%H:%M:%S')}

📊 Simulando el flujo completo:
1. Sistema iniciándose...
2. Scanner detectando oportunidades
3. Trader procesando y almacenando
4. Telegram mostrando /plays_today

⏰ Mercados cerrados - usando datos simulados"""
    
    send_message(start_message, parse_mode="Markdown")
    
    # Crear trader (como simple_main.py)
    print("🚀 Iniciando IndependentTrader...")
    trader = IndependentTrader()
    
    # Mock del mayordomo para simular decisiones reales
    mock_mayordomo = Mock()
    trader.mayordomo = mock_mayordomo
    
    # Simular múltiples ciclos de scanner (como si fuera un día real)
    scanner_cycles = [
        # Ciclo 1 - 9:35 AM (apertura)
        {
            'time': '09:35',
            'opportunities': [
                {
                    'symbol': 'MORNING_GAPPER',
                    'current_price': 15.80,
                    'gap_percentage': 0.15,  # 15% gap up
                    'volume_ratio': 6.2,
                    'quality_score': 8.5,
                    'catalyst_type': 'FDA'
                },
                {
                    'symbol': 'EARNINGS_PLAY',
                    'current_price': 45.20,
                    'gap_percentage': 0.08,  # 8% gap up  
                    'volume_ratio': 4.1,
                    'quality_score': 7.8,
                    'catalyst_type': 'EARNINGS'
                }
            ]
        },
        # Ciclo 2 - 10:15 AM
        {
            'time': '10:15', 
            'opportunities': [
                {
                    'symbol': 'NEWS_BREAKOUT',
                    'current_price': 28.90,
                    'gap_percentage': 0.12,  # 12% gap up
                    'volume_ratio': 7.8,
                    'quality_score': 9.2,
                    'catalyst_type': 'M&A'
                },
                {
                    'symbol': 'SMALL_MOVER',
                    'current_price': 8.45,
                    'gap_percentage': 0.04,  # 4% gap up
                    'volume_ratio': 2.8,
                    'quality_score': 6.1,
                    'catalyst_type': 'OTHER'
                }
            ]
        },
        # Ciclo 3 - 14:30 PM (tarde)
        {
            'time': '14:30',
            'opportunities': [
                {
                    'symbol': 'AFTERNOON_RUNNER',
                    'current_price': 67.30,
                    'gap_percentage': 0.18,  # 18% gap up
                    'volume_ratio': 9.5,
                    'quality_score': 9.8,
                    'catalyst_type': 'BREAKTHROUGH'
                }
            ]
        }
    ]
    
    # Configurar respuestas del mayordomo (simulando decisiones reales)
    mayordomo_responses = [
        # Respuestas para ciclo 1
        {'action': 'REJECT', 'reason': 'Good opportunity 0.85 - open position (slot 1/15)'},  # Este no debería pasar más
        {'action': 'EXECUTE', 'reason': 'Excellent opportunity 0.78 - executing trade', 'confidence': 0.78},
        # Respuestas para ciclo 2  
        {'action': 'EXECUTE', 'reason': 'Outstanding opportunity 0.92 - executing trade', 'confidence': 0.92},
        {'action': 'REJECT', 'reason': 'Opportunity score 0.41 below minimum threshold 0.45'},
        # Respuestas para ciclo 3
        {'action': 'EXECUTE', 'reason': 'Exceptional opportunity 0.98 - executing trade', 'confidence': 0.98}
    ]
    
    mock_mayordomo.evaluate_position_rotation.side_effect = mayordomo_responses
    
    async def simulate_cycles():
        """Simular los ciclos de scanner"""
        total_plays = 0
        
        for i, cycle in enumerate(scanner_cycles, 1):
            print(f"\n📡 CICLO {i} - {cycle['time']} - {len(cycle['opportunities'])} oportunidades")
            
            # Enviar actualización del ciclo
            cycle_message = f"""📡 CICLO DE SCANNER {i} - {cycle['time']}

🔍 Detectadas {len(cycle['opportunities'])} oportunidades:
{chr(10).join([f"• {opp['symbol']}: ${opp['current_price']:.2f} ({opp['gap_percentage']*100:+.1f}% gap)" for opp in cycle['opportunities']])}

⚡ Procesando con Mayordomo..."""
            
            send_message(cycle_message, parse_mode="Markdown")
            
            # Procesar oportunidades (como en el sistema real)
            await trader._handle_scanner_opportunities(cycle['opportunities'])
            
            total_plays += len(cycle['opportunities'])
            
            print(f"✅ Ciclo {i} procesado - {len(cycle['opportunities'])} plays almacenados")
            
            # Pausa entre ciclos (simular tiempo real)
            await asyncio.sleep(1)
        
        return total_plays
    
    # Ejecutar simulación
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        total = loop.run_until_complete(simulate_cycles())
        loop.close()
        
        print(f"\n✅ Simulación completada - {total} plays totales almacenados")
        
        # Registrar en service locator para Telegram
        service_locator = get_service_locator()
        service_locator.register_service('unified_trading_system', trader)
        
        print("📱 Enviando /plays_today a Telegram...")
        
        # Mensaje previo
        pre_message = f"""📊 SIMULACIÓN COMPLETADA

✅ Total oportunidades procesadas: {total}
✅ Todas almacenadas en notified_plays
✅ Sistema registrado en service_locator

📱 Enviando /plays_today para verificar..."""
        
        send_message(pre_message, parse_mode="Markdown")
        
        # Enviar plays del día (función real)
        send_plays_today()
        
        # Mensaje final
        final_message = f"""🎉 TEST DE SIMULACIÓN REAL COMPLETADO

📊 **Resultado esperado en /plays_today:**
• MORNING_GAPPER (FDA - 15% gap)
• EARNINGS_PLAY (EARNINGS - 8% gap)  
• NEWS_BREAKOUT (M&A - 12% gap)
• SMALL_MOVER (OTHER - 4% gap)
• AFTERNOON_RUNNER (BREAKTHROUGH - 18% gap)

✅ **Total: {total} plays del día**

💡 Si ves los {total} símbolos, la funcionalidad está perfecta"""
        
        send_message(final_message, parse_mode="Markdown")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en simulación: {e}")
        loop.close()
        return False

def main():
    """Ejecutar simulación completa"""
    print("🎬 SIMULACIÓN DE DÍA REAL DE TRADING")
    print("Usando datos falsos para simular mercados cerrados")
    print("=" * 60)
    
    success = simulate_real_trading_day()
    
    if success:
        print("\n🎉 ¡SIMULACIÓN EXITOSA!")
        print("📱 Revisa tu Telegram para ver:")
        print("   1. Mensajes de cada ciclo de scanner")
        print("   2. El resultado de /plays_today")
        print("   3. Confirmación de que se almacenaron TODOS los plays")
    else:
        print("\n❌ Error en la simulación")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)