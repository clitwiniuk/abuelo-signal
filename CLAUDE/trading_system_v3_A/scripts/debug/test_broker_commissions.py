#!/usr/bin/env python3
"""
Test específico de las comisiones del broker
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_broker_commissions():
    """Test las comisiones del broker - $2 limit, $2.5 market"""
    
    print("🔍 TESTING BROKER COMMISSIONS")
    print("=" * 60)
    print("💰 Market Orders: $2.50 per order")
    print("📝 Limit Orders: $2.00 per order")
    print("🎯 Complete Trade: Entry + Exit commissions")
    
    # Setup logging
    logging.basicConfig(level=logging.ERROR)  # Solo errores críticos
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        
        # Initialize
        await simulation_manager.initialize(create_sample_data=False)
        await sim_env['broker'].connect()
        await sim_env['data_provider'].connect()
        
        print("✅ Sistema inicializado")
        
        # Test con XXII para ver comisiones
        print(f"\n🎯 TEST CON XXII (500 barras) - Market Orders")
        print("-" * 50)
        
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=500,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats = result.get('final_stats', {})
        trades_executed = result.get('trades_executed', 0)
        total_commissions = final_stats.get('total_commissions', 0)
        
        print(f"\n📊 RESULTADOS:")
        print(f"   ✅ Trades ejecutados: {trades_executed}")
        print(f"   💰 P&L Total: ${final_stats.get('total_pnl', 0):.2f}")
        print(f"   💸 Comisiones pagadas: ${total_commissions:.2f}")
        print(f"   📈 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        
        # Análisis de comisiones
        if trades_executed > 0:
            avg_commission_per_trade = total_commissions / trades_executed
            print(f"\n💸 ANÁLISIS DE COMISIONES:")
            print(f"   Comisión promedio por orden: ${avg_commission_per_trade:.2f}")
            print(f"   Comisión esperada (Market): $2.50 por orden")
            
            if abs(avg_commission_per_trade - 2.5) < 0.1:
                print(f"   ✅ CORRECTO: Comisiones coinciden con market orders")
            else:
                print(f"   ⚠️ REVISAR: Comisión no coincide con expectativa")
            
            # Mostrar reporte detallado con comisiones
            print(f"\n" + "="*80)
            print("📋 REPORTE DETALLADO CON COMISIONES")
            print("="*80)
            simulation_manager.mock_broker.print_detailed_trade_report()
            
            # Análisis de impacto de comisiones
            trade_history = simulation_manager.mock_broker.get_detailed_trade_history()
            if trade_history:
                print(f"\n📈 IMPACTO DE COMISIONES:")
                
                total_gross_pnl = sum([t.get('gross_pnl', 0) for t in trade_history])
                total_net_pnl = sum([t.get('net_pnl', 0) for t in trade_history])
                commission_impact = total_gross_pnl - total_net_pnl
                
                print(f"   📊 P&L Bruto (sin comisiones): ${total_gross_pnl:.2f}")
                print(f"   💰 P&L Neto (con comisiones): ${total_net_pnl:.2f}")
                print(f"   💸 Impacto total comisiones: ${commission_impact:.2f}")
                print(f"   📉 Reducción por comisiones: {(commission_impact/abs(total_gross_pnl)*100) if total_gross_pnl != 0 else 0:.1f}%")
                
                # Contar trades que cambiaron de ganadores a perdedores por comisiones
                trades_affected = 0
                for trade in trade_history:
                    gross_pnl = trade.get('gross_pnl', 0)
                    net_pnl = trade.get('net_pnl', 0)
                    if gross_pnl > 0 and net_pnl <= 0:
                        trades_affected += 1
                
                if trades_affected > 0:
                    print(f"   ⚠️ Trades afectados negativamente por comisiones: {trades_affected}")
                else:
                    print(f"   ✅ Ningún trade ganador se volvió perdedor por comisiones")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            if 'sim_env' in locals():
                await sim_env['broker'].disconnect()
                await sim_env['data_provider'].disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_broker_commissions())