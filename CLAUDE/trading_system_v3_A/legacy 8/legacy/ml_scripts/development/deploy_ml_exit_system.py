#!/usr/bin/env python3
"""
Deploy ML Exit System - Activa el sistema completo de salidas inteligentes con ML
================================================================================

Integra MLExitEngine con continuous learning y actualiza el sistema de trading
para usar salidas dinámicas en lugar de reglas estáticas obsoletas.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

async def deploy_ml_exit_system():
    """Deploy completo del sistema ML Exit"""
    logger = setup_logging()
    
    print("🎯 ML EXIT SYSTEM DEPLOYMENT")
    print("=" * 70)
    print("Activando sistema completo de salidas inteligentes con ML")
    print("=" * 70)
    
    deployment_checks = {
        'config_cleaned': False,
        'ml_exit_engine_created': False,
        'continuous_learning_integration': False,
        'base_strategy_updated': False,
        'database_tables_created': False,
        'fomo_integration_verified': False,
        'system_ready_test': False
    }
    
    try:
        # Check 1: Verify config cleanup
        logger.info("🔍 Check 1: Verificando limpieza del config.ini...")
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read('config.ini')
            
            # Check for new ML Exit System section
            if config.has_section('ML_EXIT_SYSTEM'):
                deployment_checks['config_cleaned'] = True
                logger.info("✅ Config.ini limpio con sección ML_EXIT_SYSTEM")
            else:
                logger.error("❌ Falta sección ML_EXIT_SYSTEM en config.ini")
                
        except Exception as e:
            logger.error(f"❌ Error verificando config: {e}")
        
        # Check 2: ML Exit Engine creation
        logger.info("🔍 Check 2: Verificando MLExitEngine...")
        try:
            from core.ml_exit_engine import MLExitEngine, get_global_ml_exit_engine
            
            ml_exit_engine = get_global_ml_exit_engine()
            if ml_exit_engine:
                deployment_checks['ml_exit_engine_created'] = True
                logger.info(f"✅ MLExitEngine creado para {len(ml_exit_engine.strategies)} estrategias")
            else:
                logger.error("❌ MLExitEngine no se pudo crear")
                
        except Exception as e:
            logger.error(f"❌ Error creando MLExitEngine: {e}")
        
        # Check 3: Continuous Learning integration
        logger.info("🔍 Check 3: Verificando integración con Continuous Learning...")
        try:
            from core.continuous_learning_engine import get_global_learning_engine, record_trade_exit_feedback
            
            learning_engine = get_global_learning_engine()
            if hasattr(learning_engine, 'ml_exit_engine'):
                deployment_checks['continuous_learning_integration'] = True
                logger.info("✅ Continuous Learning integrado con ML Exit")
            else:
                logger.error("❌ Continuous Learning no integrado con ML Exit")
                
        except Exception as e:
            logger.error(f"❌ Error verificando Continuous Learning: {e}")
        
        # Check 4: Base Strategy updated
        logger.info("🔍 Check 4: Verificando BaseStrategy actualizada...")
        try:
            from strategies.base import BaseStrategy
            import inspect
            
            # Check if BaseStrategy class has required methods
            base_methods = [method for method in dir(BaseStrategy) if not method.startswith('_')]
            has_exit_methods = (
                'should_exit_position' in base_methods and
                hasattr(BaseStrategy, '__init__')
            )
            
            if has_exit_methods:
                deployment_checks['base_strategy_updated'] = True
                logger.info("✅ BaseStrategy actualizada con ML Exit methods")
            else:
                logger.error("❌ BaseStrategy no tiene métodos ML Exit")
                
        except Exception as e:
            logger.error(f"❌ Error verificando BaseStrategy: {e}")
        
        # Check 5: Database tables
        logger.info("🔍 Check 5: Verificando tablas de base de datos...")
        try:
            import sqlite3
            
            with sqlite3.connect('trading_data.db') as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                required_tables = ['exit_feedback', 'exit_model_performance']
                missing_tables = [t for t in required_tables if t not in tables]
                
                if not missing_tables:
                    deployment_checks['database_tables_created'] = True
                    logger.info("✅ Tablas de ML Exit creadas correctamente")
                else:
                    logger.error(f"❌ Faltan tablas: {missing_tables}")
                    
        except Exception as e:
            logger.error(f"❌ Error verificando base de datos: {e}")
        
        # Check 6: FOMO Integration
        logger.info("🔍 Check 6: Verificando integración con FOMO Detector...")
        try:
            from core.fomo_detector import FOMODetector
            from core.ml_exit_engine import MLExitEngine
            
            ml_engine = MLExitEngine()
            if hasattr(ml_engine, 'fomo_detector'):
                deployment_checks['fomo_integration_verified'] = True
                logger.info("✅ FOMO Detector integrado correctamente")
            else:
                logger.error("❌ FOMO Detector no integrado")
                
        except Exception as e:
            logger.error(f"❌ Error verificando FOMO integration: {e}")
        
        # Check 7: System readiness test
        logger.info("🔍 Check 7: Test de sistema completo...")
        try:
            from core.interfaces import Position, MarketData
            from datetime import datetime, timezone
            
            # Create test data
            test_position = Position(
                symbol="TEST",
                quantity=100,
                avg_price=10.0,
                entry_time=datetime.now(timezone.utc),
                strategy="test_strategy"
            )
            
            test_market_data = MarketData(
                symbol="TEST",
                timestamp=datetime.now(timezone.utc),
                open=10.5,
                high=11.0,
                low=10.0,
                close=10.8,
                volume=100000
            )
            
            # Test ML Exit decision
            ml_engine = get_global_ml_exit_engine()
            decision = ml_engine.should_exit(test_position, test_market_data, [test_market_data])
            
            if 'should_exit' in decision:
                deployment_checks['system_ready_test'] = True
                logger.info("✅ Sistema ML Exit funcional")
            else:
                logger.error("❌ Sistema ML Exit no responde correctamente")
                
        except Exception as e:
            logger.error(f"❌ Error en test de sistema: {e}")
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 DEPLOYMENT SUMMARY")
        print("=" * 70)
        
        passed_checks = sum(deployment_checks.values())
        total_checks = len(deployment_checks)
        
        for check, status in deployment_checks.items():
            status_icon = "✅" if status else "❌"
            print(f"{status_icon} {check.replace('_', ' ').title()}")
        
        print(f"\n🎯 OVERALL STATUS: {passed_checks}/{total_checks} checks passed")
        
        if passed_checks == total_checks:
            print("\n🚀 ML EXIT SYSTEM FULLY DEPLOYED!")
            print("\nEl sistema está listo para:")
            print("• Salidas inteligentes basadas en ML por estrategia")
            print("• Integración con FOMO detection avanzado")
            print("• Aprendizaje continuo de patrones de salida")
            print("• Fallback automático a reglas estáticas si ML falla")
            print("• Feedback learning para mejora continua")
            
            print("\n💡 NEXT STEPS:")
            print("• Ejecutar trader_main.py para comenzar trading con ML exits")
            print("• Monitorear logs para verificar decisiones ML")
            print("• Revisar performance en dashboard después de 50+ trades")
            
        else:
            print(f"\n⚠️ DEPLOYMENT INCOMPLETE: {total_checks - passed_checks} issues detected")
            print("Revisar errores arriba y corregir antes de usar ML Exit system")
        
        print("=" * 70)
        
        return passed_checks == total_checks
        
    except Exception as e:
        logger.error(f"❌ Error crítico durante deployment: {e}")
        return False

async def main():
    """Main deployment function"""
    print("Starting ML Exit System deployment...")
    success = await deploy_ml_exit_system()
    
    if success:
        print("\n✅ Deployment completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Deployment failed. Check logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())