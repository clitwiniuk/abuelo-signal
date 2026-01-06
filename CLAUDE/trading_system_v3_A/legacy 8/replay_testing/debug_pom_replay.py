#!/usr/bin/env python3
"""
Debug Replay - POM específico con logs detallados

Ejecuta replay solo para POM con logging DEBUG para ver
exactamente por qué el worker rechaza la entrada.
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("\n" + "="*80)
    print("🔍 DEBUG REPLAY: POM @ 2025-12-05")
    print("="*80 + "\n")
    
    # Initialize Replay Engine with verbose=True
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db',
        verbose=True
    )
    
    # Run replay ONLY for POM
    session = engine.replay_day(
        date='2025-12-05',
        worker_names=['buy_the_dip'],
        symbols=['POM']  # Solo POM
    )
    
    print("\n" + "="*80)
    print("📊 RESULTADOS")
    print("="*80)
    
    event = session.get_event('POM')
    if event:
        print(f"\nDecisiones totales: {event.decisions_made}")
        print(f"Entradas aprobadas: {event.entries_approved}")
        print(f"Entradas rechazadas: {event.entries_rejected}")
        
        # Analizar razones de rechazo
        decisions = event.get_all_decisions()
        
        if decisions:
            print(f"\n🚫 ANÁLISIS DE RECHAZOS:")
            print("-" * 80)
            
            # Agrupar por razones
            rejection_reasons = {}
            for decision in decisions:
                if decision.decision_type == 'REJECTED':
                    for reason, msg in decision.checks_failed.items():
                        if reason not in rejection_reasons:
                            rejection_reasons[reason] = {
                                'count': 0,
                                'examples': []
                            }
                        rejection_reasons[reason]['count'] += 1
                        if len(rejection_reasons[reason]['examples']) < 3:
                            rejection_reasons[reason]['examples'].append({
                                'time': decision.timestamp,
                                'message': msg
                            })
            
            # Mostrar razones ordenadas por frecuencia
            for reason, data in sorted(rejection_reasons.items(), 
                                      key=lambda x: x[1]['count'], 
                                      reverse=True):
                print(f"\n{reason}: {data['count']} veces")
                print("  Ejemplos:")
                for ex in data['examples']:
                    print(f"    - {ex['time'].strftime('%H:%M:%S')}: {ex['message']}")
        
        # Buscar la barra de 15:44 específicamente
        print(f"\n🎯 BARRA DE ENTRADA ESPERADA (15:44 ET):")
        print("-" * 80)
        
        entry_decisions = [d for d in decisions 
                          if d.timestamp.hour == 15 and d.timestamp.minute == 44]
        
        if entry_decisions:
            for decision in entry_decisions:
                print(f"\nTimestamp: {decision.timestamp}")
                print(f"Decision: {decision.decision_type}")
                print(f"Should enter: {decision.should_enter}")
                
                if decision.checks_failed:
                    print("\nFiltros que fallaron:")
                    for check, msg in decision.checks_failed.items():
                        print(f"  ❌ {check}: {msg}")
                
                if decision.checks_passed:
                    print("\nFiltros que pasaron:")
                    for check, passed in decision.checks_passed.items():
                        if passed:
                            print(f"  ✅ {check}")
        else:
            print("⚠️  No se encontraron decisiones para la barra de 15:44")
    
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    main()
