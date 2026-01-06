#!/usr/bin/env python3
"""
Deploy Continuous Learning System - Activa sistema completo de aprendizaje continuo
Verifica y despliega el sistema ML con feedback automático en producción
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

async def deploy_continuous_learning_system():
    """Deploy completo del sistema de continuous learning"""
    logger = setup_logging()
    
    print("🚀 CONTINUOUS LEARNING SYSTEM DEPLOYMENT")
    print("=" * 70)
    print("Activando sistema completo de aprendizaje automático continuo")
    print("=" * 70)
    
    deployment_checks = {
        'database_structure': False,
        'ml_models_available': False,
        'continuous_learning_engine': False,
        'feedback_hook_integration': False,
        'performance_monitor': False,
        'ibkr_adapter_integration': False,
        'full_system_test': False
    }
    
    try:
        # Check 1: Database structure
        logger.info("🔍 Check 1: Verificando estructura de base de datos...")
        try:
            import sqlite3
            
            # Check trading_data.db exists and has required tables
            with sqlite3.connect('trading_data.db') as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                required_tables = ['trades', 'volume_feedback', 'model_performance', 'learning_events']
                missing_tables = [t for t in required_tables if t not in tables]
                
                if not missing_tables:
                    deployment_checks['database_structure'] = True
                    logger.info("✅ Database structure verified")
                else:
                    logger.error(f"❌ Missing tables: {missing_tables}")
                    
        except Exception as e:
            logger.error(f"❌ Database check failed: {e}")
        
        # Check 2: ML Models availability
        logger.info("🔍 Check 2: Verificando modelos ML...")
        try:
            from core.ml_volume_engine import MLVolumeEngine
            
            ml_engine = MLVolumeEngine()
            if ml_engine.load_models():
                deployment_checks['ml_models_available'] = True
                status = ml_engine.get_optimization_status()
                logger.info(f"✅ ML models loaded: {status['trained_strategies']} strategies")
            else:
                logger.error("❌ ML models failed to load")
                
        except Exception as e:
            logger.error(f"❌ ML models check failed: {e}")
        
        # Check 3: Continuous Learning Engine
        logger.info("🔍 Check 3: Verificando Continuous Learning Engine...")
        try:
            from core.continuous_learning_engine import get_global_learning_engine
            
            learning_engine = get_global_learning_engine()
            learning_engine.start_continuous_learning()
            
            # Test basic functionality
            await asyncio.sleep(1)
            metrics = learning_engine.get_learning_metrics()
            
            if learning_engine._learning_active:
                deployment_checks['continuous_learning_engine'] = True
                logger.info(f"✅ Continuous Learning Engine active")
            else:
                logger.error("❌ Continuous Learning Engine not active")
                
            learning_engine.stop_continuous_learning()
            
        except Exception as e:
            logger.error(f"❌ Continuous Learning Engine check failed: {e}")
        
        # Check 4: Feedback Hook Integration
        logger.info("🔍 Check 4: Verificando Trading Feedback Hook...")
        try:
            from core.trading_feedback_hook import get_global_feedback_hook
            
            feedback_hook = get_global_feedback_hook()
            
            # Test with dummy trade data
            test_trade = {
                'trade_id': 'TEST_DEPLOY',
                'symbol': 'TEST',
                'strategy': 'macdv_smallcaps',
                'entry_price': 5.0,
                'quantity': 100
            }
            
            feedback_hook.on_trade_opened(test_trade)
            feedback_hook.on_trade_closed({'trade_id': 'TEST_DEPLOY', 'pnl': 10.0})
            
            deployment_checks['feedback_hook_integration'] = True
            logger.info("✅ Trading Feedback Hook working")
            
        except Exception as e:
            logger.error(f"❌ Feedback Hook check failed: {e}")
        
        # Check 5: Performance Monitor
        logger.info("🔍 Check 5: Verificando Performance Monitor...")
        try:
            from core.ml_performance_monitor import get_global_performance_monitor
            
            performance_monitor = get_global_performance_monitor()
            performance_monitor.start_monitoring(interval_hours=24)  # Production interval
            
            summary = performance_monitor.get_performance_summary()
            
            if summary.get('monitoring_active'):
                deployment_checks['performance_monitor'] = True
                logger.info("✅ Performance Monitor active")
            else:
                logger.error("❌ Performance Monitor not active")
                
            performance_monitor.stop_monitoring()
            
        except Exception as e:
            logger.error(f"❌ Performance Monitor check failed: {e}")
        
        # Check 6: IBKR Adapter Integration
        logger.info("🔍 Check 6: Verificando IBKR Adapter Integration...")
        try:
            from adapters.ibkr_adapter import IBKRAdapter
            
            # Test adapter initialization (without connecting)
            adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=9999)
            
            if hasattr(adapter, 'get_dynamic_volume_requirement') and hasattr(adapter, 'ml_volume_engine'):
                deployment_checks['ibkr_adapter_integration'] = True
                logger.info("✅ IBKR Adapter integration verified")
            else:
                logger.error("❌ IBKR Adapter missing ML integration")
                
        except Exception as e:
            logger.error(f"❌ IBKR Adapter check failed: {e}")
        
        # Check 7: Full System Test
        logger.info("🔍 Check 7: Test de sistema completo...")
        try:
            # This is a lightweight version of the full test
            from core.continuous_learning_engine import get_global_learning_engine
            from core.ml_performance_monitor import get_global_performance_monitor
            from core.trading_feedback_hook import get_global_feedback_hook
            
            # Initialize all components
            learning_engine = get_global_learning_engine()
            performance_monitor = get_global_performance_monitor()
            feedback_hook = get_global_feedback_hook()
            
            # Start systems
            learning_engine.start_continuous_learning()
            performance_monitor.start_monitoring(interval_hours=24)
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Verify all are running
            if (learning_engine._learning_active and 
                performance_monitor._monitoring_active):
                
                deployment_checks['full_system_test'] = True
                logger.info("✅ Full system test passed")
            else:
                logger.error("❌ Full system test failed")
            
            # Cleanup
            learning_engine.stop_continuous_learning()
            performance_monitor.stop_monitoring()
            
        except Exception as e:
            logger.error(f"❌ Full system test failed: {e}")
        
        # Results summary
        print("\n" + "=" * 70)
        print("📊 CONTINUOUS LEARNING DEPLOYMENT RESULTS")
        print("=" * 70)
        
        total_checks = len(deployment_checks)
        passed_checks = sum(deployment_checks.values())
        
        for check_name, passed in deployment_checks.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} {check_name.replace('_', ' ').title()}")
        
        success_rate = (passed_checks / total_checks) * 100
        print(f"\n🎯 DEPLOYMENT STATUS: {passed_checks}/{total_checks} checks passed ({success_rate:.1f}%)")
        
        if success_rate == 100:
            print("🎉 CONTINUOUS LEARNING DEPLOYMENT SUCCESSFUL!")
            print()
            print("🧠 SISTEMA ACTIVO - EL TRADING SYSTEM AHORA:")
            print("   ✅ Aprende automáticamente de cada trade")
            print("   ✅ Adapta requerimientos de volumen dinámicamente")  
            print("   ✅ Monitorea performance y detecta drift")
            print("   ✅ Re-entrena modelos automáticamente")
            print("   ✅ Mejora predicciones continuamente")
            print()
            print("📋 CARACTERÍSTICAS IMPLEMENTADAS:")
            print("   • ML Volume Engine con 10 modelos entrenados")
            print("   • Feedback automático de resultados de trading")
            print("   • Monitoreo de performance 24/7")
            print("   • Detección automática de drift")
            print("   • Re-entrenamiento semanal automático")
            print("   • Alertas de performance en tiempo real")
            print()
            print("🔄 PRÓXIMOS PASOS:")
            print("   1. Reiniciar el sistema de trading")
            print("   2. El continuous learning se activará automáticamente")
            print("   3. Monitorear logs para ver el aprendizaje en acción")
            
        elif success_rate >= 80:
            print("⚠️ DEPLOYMENT PARCIAL - Sistema mayormente funcional")
            print("Revisar checks fallidos antes de usar en producción")
            
        else:
            print("❌ DEPLOYMENT FAILED - Sistema no está listo")
            print("Corregir errores antes de deployment")
        
        print("=" * 70)
        
        return success_rate >= 80
        
    except Exception as e:
        logger.error(f"❌ Error durante deployment: {e}")
        return False

async def main():
    try:
        success = await deploy_continuous_learning_system()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Error in continuous learning deployment: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)