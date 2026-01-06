#!/usr/bin/env python3
"""
Demo del Sistema Completo de Quality Trading con Learning
=========================================================

Demostración completa que muestra:
1. Análisis avanzado de calidad con factores múltiples
2. Sistema de learning automático
3. Tracking de predicciones y resultados
4. Optimización de pesos basada en performance

Este demo usa tickers reales para mostrar el sistema funcionando.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir / "quality_core"))

from quality_core.advanced_setup_analyzer import analyze_setup_comprehensive
from quality_core.learning_system import AutoLearningSystem

def demo_ppsi_analysis():
    """Demo del caso PPSI que motivó las mejoras"""
    print("🔍 DEMO: Análisis PPSI (Caso Problemático Original)")
    print("=" * 60)
    print("Situación: PPSI con +42.1% gap pero cayó durante el día")
    print("Objetivo: Mostrar cómo el nuevo sistema detecta esto como bajo quality\n")
    
    # Usar datos del caso real PPSI
    result = analyze_setup_comprehensive(
        ticker="PPSI",
        current_price=4.42,
        current_volume=80_600_000,
        premarket_gap_pct=42.1
    )
    
    print(f"📊 Resultados PPSI:")
    print(f"   🎯 Grade Final: {result['grade']}")
    print(f"   📈 Score: {result['overall_score']}/100")
    print(f"   💡 Recomendación: {result['recommendation']}")
    print(f"   ⚠️  Nivel de Riesgo: {result['risk_level']}")
    print(f"   💰 Tamaño Posición: {result['position_size']}")
    
    if result['red_flags']:
        print(f"\n🔴 Red Flags Detectadas:")
        for flag in result['red_flags']:
            print(f"   • {flag}")
    
    if result['key_factors']:
        print(f"\n✅ Factores Positivos:")
        for factor in result['key_factors']:
            print(f"   • {factor}")
    
    # Información de consolidación
    consol_months = result.get('consolidation_months', 0)
    if consol_months > 0:
        print(f"\n📈 Consolidación: {consol_months:.1f} meses")
    else:
        print(f"\n📉 Consolidación: Insuficiente historial de consolidación")
    
    # Target analysis
    if result.get('nearest_target'):
        target = result['nearest_target']
        print(f"🎯 Próximo Target: ${target['price']:.2f} (+{target['distance_pct']:.0f}%)")
    
    return result

def demo_learning_system():
    """Demo del sistema de aprendizaje"""
    print(f"\n🧠 DEMO: Sistema de Aprendizaje Automático")
    print("=" * 60)
    
    # Inicializar sistema con base de datos de demo
    db_path = "demo_learning.db"
    auto_system = AutoLearningSystem(db_path)
    
    print(f"🗄️  Base de datos de learning: {db_path}")
    
    # Simular múltiples análisis para mostrar el learning
    demo_tickers = [
        ("AAPL", 150.0, 50_000_000, 5.2),
        ("TSLA", 180.0, 25_000_000, 8.7),
        ("NVDA", 400.0, 30_000_000, 12.3),
        ("AMD", 80.0, 45_000_000, 15.8),
        ("MSFT", 300.0, 20_000_000, 3.1)
    ]
    
    print(f"📊 Simulando análisis de {len(demo_tickers)} setups:")
    
    predictions = []
    for ticker, price, volume, gap in demo_tickers:
        try:
            # Realizar análisis con learning system
            result = analyze_setup_comprehensive(
                ticker=ticker,
                current_price=price,
                current_volume=volume,
                premarket_gap_pct=gap,
                learning_db_path=db_path
            )
            
            predictions.append(result)
            print(f"   ✅ {ticker}: {result['grade']} ({result['overall_score']}/100)")
            
        except Exception as e:
            print(f"   ❌ {ticker}: Error - {e}")
    
    # Mostrar estadísticas del sistema de learning
    stats = auto_system.get_system_stats()
    print(f"\n📈 Estadísticas del Sistema de Learning:")
    print(f"   📊 Total Predicciones: {stats['total_predictions']}")
    print(f"   🧠 Learning Habilitado: {'✅ Sí' if stats['learning_enabled'] else '❌ No (necesita más datos)'}")
    print(f"   ⚖️  Pesos Actuales:")
    for factor, weight in stats['current_weights'].items():
        print(f"      • {factor.title()}: {weight:.1%}")
    
    return predictions, auto_system

def demo_weight_evolution():
    """Demo de evolución de pesos a medida que el sistema aprende"""
    print(f"\n⚖️  DEMO: Evolución de Pesos del Sistema")
    print("=" * 60)
    
    print("🎯 Filosofía del Sistema:")
    print("• Consolildation (30%): Meses de acumulación = Mejor calidad")
    print("• Timing (25%): Premarket exhausted vs Regular hours strength") 
    print("• Volume (25%): Institutional interest & accumulation patterns")
    print("• News (20%): Catalyst quality & negative risk assessment")
    
    print(f"\n💡 Key Insight del Usuario:")
    print("'Un gap grande sin consolidación previa es peor que un gap pequeño")
    print("con meses de acumulación y room to run hacia resistencias históricas.'")
    
    print(f"\n🔄 A medida que el sistema acumula resultados reales:")
    print("• Los pesos se ajustan automáticamente basado en correlaciones")
    print("• Factores más predictivos reciben mayor peso")
    print("• El sistema aprende sin sesgos de look-ahead")
    print("• Solo usa datos históricos para optimización")

def demo_monitoring_tools():
    """Demo de herramientas de monitoreo"""
    print(f"\n🔧 DEMO: Herramientas de Monitoreo")
    print("=" * 60)
    
    print("📊 Comandos disponibles para monitoreo:")
    print("   python quality_core/learning_monitor.py stats")
    print("   python quality_core/learning_monitor.py predictions --limit 20")
    print("   python quality_core/learning_monitor.py update --dry-run")
    print("   python quality_core/learning_monitor.py export results.json")
    
    print(f"\n🎯 Integración con quality_trading_standalone.py:")
    print("• El sistema se integra automáticamente")
    print("• Cada análisis se loggea para aprendizaje")
    print("• Los pesos se actualizan basado en resultados")
    print("• Monitoreo en tiempo real del performance")

def main():
    """Demo completo del sistema integrado"""
    print("🚀 DEMO COMPLETO: QUALITY TRADING SYSTEM CON LEARNING")
    print("=" * 70)
    print(f"⏰ Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Demo 1: Análisis PPSI
        ppsi_result = demo_ppsi_analysis()
        
        # Demo 2: Sistema de Learning
        predictions, learning_system = demo_learning_system()
        
        # Demo 3: Evolución de pesos
        demo_weight_evolution()
        
        # Demo 4: Herramientas de monitoreo
        demo_monitoring_tools()
        
        # Resumen final
        print(f"\n🎉 DEMO COMPLETADO EXITOSAMENTE")
        print("=" * 70)
        print("✅ Sistema de análisis avanzado funcionando")
        print("✅ Learning system integrado y operacional") 
        print("✅ Tracking de predicciones implementado")
        print("✅ Herramientas de monitoreo disponibles")
        
        print(f"\n💼 Para usar en producción:")
        print("1. Ejecuta: streamlit run quality_trading_standalone.py")
        print("2. Usa datos reales de ProRealTime")
        print("3. Monitorea con: python quality_core/learning_monitor.py stats")
        print("4. El sistema aprenderá automáticamente de los resultados")
        
        print(f"\n🗄️  Base de datos de demo: demo_learning.db")
        print("🔧 Usa learning_monitor.py para inspeccionar los datos")
        
    except Exception as e:
        print(f"❌ Error en demo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()