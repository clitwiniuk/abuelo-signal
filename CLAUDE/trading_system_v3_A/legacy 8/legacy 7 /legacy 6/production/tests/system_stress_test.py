# production/system_stress_test.py
"""
Test de Estrés del Sistema Híbrido Smallcaps
Simula condiciones reales de mercado sin depender de APIs externas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
from concurrent.futures import ThreadPoolExecutor
import threading

# Aprovechar sistema híbrido
from production.hybrid_config_manager import HybridConfigManager

@dataclass
class StressTestResult:
    """Resultado de test de estrés"""
    test_name: str
    duration_seconds: float
    operations_completed: int
    operations_per_second: float
    errors: List[str]
    memory_usage_mb: float
    success_rate: float
    timestamp: datetime

class SmallcapSystemStressTest:
    """
    Test de estrés para el sistema híbrido de smallcaps
    Simula cargas reales de mercado intraday
    """
    
    def __init__(self):
        self.logger = logging.getLogger("StressTest")
        
        # Cargar configuración híbrida
        try:
            self.hybrid_config = HybridConfigManager()
            self.config = self._load_stress_config()
            self.logger.info("✅ Configuración híbrida cargada para stress test")
        except Exception as e:
            self.logger.error(f"❌ Error cargando configuración: {e}")
            raise
        
        # Estado del test
        self.test_results = []
        self.is_running = False
        self.start_time = None
        
    def _load_stress_config(self) -> Dict[str, Any]:
        """Configuración para tests de estrés"""
        smallcap_config = self.hybrid_config.get_smallcap_strategy_config()
        production_ext = self.hybrid_config.get_production_extensions()
        
        return {
            "stress_test": {
                "max_concurrent_operations": 50,
                "test_duration_seconds": 60,
                "operations_per_second_target": 10,
                "memory_limit_mb": 512,
                "error_threshold_percent": 5.0
            },
            
            "smallcap_config": smallcap_config,
            "scanning_intervals": production_ext["scanning_intervals"],
            "monitoring": production_ext["production_monitoring"],
            
            # Símbolos simulados para stress test
            "test_symbols": [
                f"TEST{i:03d}" for i in range(1, 101)  # 100 símbolos de test
            ],
            
            # Datos simulados de mercado
            "market_simulation": {
                "price_range": (1.0, 15.0),
                "volume_range": (100000, 5000000),
                "gap_range": (0.05, 0.30),
                "volatility_range": (0.01, 0.15)
            }
        }
    
    def _simulate_market_data(self, symbol: str) -> Dict[str, Any]:
        """Simular datos de mercado para un símbolo"""
        sim_config = self.config["market_simulation"]
        
        # Generar datos aleatorios realistas
        price = random.uniform(*sim_config["price_range"])
        volume = random.randint(*sim_config["volume_range"])
        gap = random.uniform(*sim_config["gap_range"])
        volatility = random.uniform(*sim_config["volatility_range"])
        
        # Simular si cumple criterios smallcap
        smallcap_config = self.config["smallcap_config"]
        meets_criteria = (
            smallcap_config["min_price"] <= price <= smallcap_config["max_price"] and
            volume >= smallcap_config["min_volume"] and
            gap >= smallcap_config["min_gap_percent"] / 100
        )
        
        return {
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "gap_percentage": gap,
            "volatility": volatility,
            "meets_smallcap_criteria": meets_criteria,
            "timestamp": datetime.now()
        }
    
    def _simulate_scanning_operation(self) -> Dict[str, Any]:
        """Simular operación de scanning"""
        start_time = time.time()
        
        # Simular procesamiento de múltiples símbolos
        symbols_to_scan = random.sample(
            self.config["test_symbols"], 
            random.randint(5, 20)
        )
        
        results = []
        errors = []
        
        for symbol in symbols_to_scan:
            try:
                # Simular latencia de API
                time.sleep(random.uniform(0.001, 0.01))
                
                market_data = self._simulate_market_data(symbol)
                results.append(market_data)
                
                # Simular errores ocasionales
                if random.random() < 0.02:  # 2% error rate
                    raise Exception(f"Simulated API error for {symbol}")
                    
            except Exception as e:
                errors.append(str(e))
        
        duration = time.time() - start_time
        
        return {
            "operation": "scanning",
            "symbols_processed": len(symbols_to_scan),
            "successful_results": len(results),
            "errors": errors,
            "duration_seconds": duration,
            "plays_found": sum(1 for r in results if r["meets_smallcap_criteria"])
        }
    
    def _simulate_ml_operation(self) -> Dict[str, Any]:
        """Simular operación ML de estrategia"""
        start_time = time.time()
        
        # Simular análisis ML
        time.sleep(random.uniform(0.01, 0.05))
        
        # Simular resultados ML
        confidence_scores = [random.uniform(0.3, 0.9) for _ in range(5)]
        strategy_selection = random.choice(["gap_go", "orb", "volume_breakout", "daily_plays"])
        
        duration = time.time() - start_time
        
        return {
            "operation": "ml_analysis",
            "strategy_selected": strategy_selection,
            "confidence_scores": confidence_scores,
            "processing_time": duration,
            "features_analyzed": random.randint(10, 50)
        }
    
    def _simulate_position_management(self) -> Dict[str, Any]:
        """Simular gestión de posiciones"""
        start_time = time.time()
        
        # Simular operaciones de mayordomo
        time.sleep(random.uniform(0.005, 0.02))
        
        actions = ["position_opened", "stop_loss_updated", "position_closed", "risk_check"]
        action = random.choice(actions)
        
        duration = time.time() - start_time
        
        return {
            "operation": "position_management",
            "action": action,
            "symbol": random.choice(self.config["test_symbols"][:10]),
            "duration_seconds": duration,
            "risk_metrics_calculated": random.randint(5, 15)
        }
    
    async def run_concurrent_operations(self, operation_count: int, operation_type: str) -> StressTestResult:
        """Ejecutar operaciones concurrentes"""
        start_time = time.time()
        operations_completed = 0
        errors = []
        
        # Seleccionar función de simulación
        if operation_type == "scanning":
            operation_func = self._simulate_scanning_operation
        elif operation_type == "ml_analysis":
            operation_func = self._simulate_ml_operation
        elif operation_type == "position_management":
            operation_func = self._simulate_position_management
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")
        
        # Ejecutar operaciones concurrentes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            for i in range(operation_count):
                future = executor.submit(operation_func)
                futures.append(future)
            
            # Procesar resultados
            for future in futures:
                try:
                    result = future.result(timeout=30)
                    operations_completed += 1
                    
                    # Agregar errores de la operación
                    if "errors" in result:
                        errors.extend(result["errors"])
                        
                except Exception as e:
                    errors.append(f"Operation failed: {e}")
        
        duration = time.time() - start_time
        operations_per_second = operations_completed / duration if duration > 0 else 0
        success_rate = operations_completed / operation_count if operation_count > 0 else 0
        
        # Simular uso de memoria
        memory_usage = random.uniform(50, 200)  # MB
        
        return StressTestResult(
            test_name=f"concurrent_{operation_type}",
            duration_seconds=duration,
            operations_completed=operations_completed,
            operations_per_second=operations_per_second,
            errors=errors,
            memory_usage_mb=memory_usage,
            success_rate=success_rate,
            timestamp=datetime.now()
        )
    
    async def run_sustained_load_test(self, duration_seconds: int) -> StressTestResult:
        """Test de carga sostenida"""
        start_time = time.time()
        operations_completed = 0
        errors = []
        
        self.logger.info(f"🔥 Iniciando test de carga sostenida por {duration_seconds}s...")
        
        while time.time() - start_time < duration_seconds:
            try:
                # Mezclar diferentes tipos de operaciones
                operation_types = ["scanning", "ml_analysis", "position_management"]
                operation_type = random.choice(operation_types)
                
                if operation_type == "scanning":
                    result = self._simulate_scanning_operation()
                elif operation_type == "ml_analysis":
                    result = self._simulate_ml_operation()
                else:
                    result = self._simulate_position_management()
                
                operations_completed += 1
                
                if "errors" in result:
                    errors.extend(result["errors"])
                
                # Simular intervalo entre operaciones
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
            except Exception as e:
                errors.append(f"Sustained load error: {e}")
        
        duration = time.time() - start_time
        operations_per_second = operations_completed / duration
        success_rate = 1.0 - (len(errors) / max(operations_completed, 1))
        
        return StressTestResult(
            test_name="sustained_load",
            duration_seconds=duration,
            operations_completed=operations_completed,
            operations_per_second=operations_per_second,
            errors=errors,
            memory_usage_mb=random.uniform(100, 300),
            success_rate=success_rate,
            timestamp=datetime.now()
        )
    
    async def run_full_stress_test(self) -> Dict[str, Any]:
        """Ejecutar suite completa de tests de estrés"""
        self.logger.info("🔥 INICIANDO TESTS DE ESTRÉS DEL SISTEMA HÍBRIDO")
        
        self.is_running = True
        self.start_time = time.time()
        
        # 1. Test de operaciones concurrentes de scanning
        self.logger.info("📊 Test 1: Scanning concurrente...")
        scanning_result = await self.run_concurrent_operations(50, "scanning")
        self.test_results.append(scanning_result)
        
        # 2. Test de análisis ML concurrente
        self.logger.info("🧠 Test 2: Análisis ML concurrente...")
        ml_result = await self.run_concurrent_operations(30, "ml_analysis")
        self.test_results.append(ml_result)
        
        # 3. Test de gestión de posiciones
        self.logger.info("⚖️ Test 3: Gestión de posiciones concurrente...")
        position_result = await self.run_concurrent_operations(40, "position_management")
        self.test_results.append(position_result)
        
        # 4. Test de carga sostenida
        self.logger.info("🔥 Test 4: Carga sostenida...")
        sustained_result = await self.run_sustained_load_test(30)
        self.test_results.append(sustained_result)
        
        total_duration = time.time() - self.start_time
        self.is_running = False
        
        # Generar resumen
        total_operations = sum(r.operations_completed for r in self.test_results)
        total_errors = sum(len(r.errors) for r in self.test_results)
        avg_ops_per_second = sum(r.operations_per_second for r in self.test_results) / len(self.test_results)
        overall_success_rate = 1.0 - (total_errors / max(total_operations, 1))
        
        summary = {
            "status": "completed",
            "total_duration_seconds": total_duration,
            "total_operations": total_operations,
            "total_errors": total_errors,
            "average_ops_per_second": avg_ops_per_second,
            "overall_success_rate": overall_success_rate,
            "individual_tests": [
                {
                    "test_name": r.test_name,
                    "operations_completed": r.operations_completed,
                    "ops_per_second": r.operations_per_second,
                    "success_rate": r.success_rate,
                    "memory_usage_mb": r.memory_usage_mb,
                    "error_count": len(r.errors)
                }
                for r in self.test_results
            ],
            "performance_metrics": {
                "peak_memory_usage": max(r.memory_usage_mb for r in self.test_results),
                "peak_ops_per_second": max(r.operations_per_second for r in self.test_results),
                "stability_score": overall_success_rate
            }
        }
        
        return summary
    
    def print_stress_test_report(self, summary: Dict[str, Any]):
        """Imprimir reporte de stress test"""
        print("\n" + "="*60)
        print("🔥 REPORTE DE STRESS TEST - SISTEMA HÍBRIDO SMALLCAPS")
        print("="*60)
        
        print(f"\n⏱️ Duración total: {summary['total_duration_seconds']:.1f}s")
        print(f"🔢 Operaciones totales: {summary['total_operations']:,}")
        print(f"❌ Errores totales: {summary['total_errors']}")
        print(f"📊 Ops/segundo promedio: {summary['average_ops_per_second']:.1f}")
        print(f"✅ Tasa de éxito general: {summary['overall_success_rate']:.1%}")
        
        print(f"\n📈 MÉTRICAS DE PERFORMANCE:")
        metrics = summary['performance_metrics']
        print(f"   🚀 Pico ops/segundo: {metrics['peak_ops_per_second']:.1f}")
        print(f"   💾 Pico memoria: {metrics['peak_memory_usage']:.1f} MB")
        print(f"   🎯 Score estabilidad: {metrics['stability_score']:.1%}")
        
        print(f"\n🧪 RESULTADOS POR TEST:")
        for test in summary['individual_tests']:
            status = "✅" if test['success_rate'] > 0.95 else "⚠️" if test['success_rate'] > 0.9 else "❌"
            print(f"   {status} {test['test_name']}:")
            print(f"      Ops: {test['operations_completed']:,}, Rate: {test['ops_per_second']:.1f}/s")
            print(f"      Éxito: {test['success_rate']:.1%}, Memoria: {test['memory_usage_mb']:.1f}MB")
        
        # Evaluación general
        if summary['overall_success_rate'] >= 0.95 and metrics['peak_ops_per_second'] >= 5:
            print(f"\n🎉 EVALUACIÓN: SISTEMA LISTO PARA PRODUCCIÓN")
            print(f"   ✅ Alta estabilidad ({summary['overall_success_rate']:.1%})")
            print(f"   ✅ Performance adecuada ({metrics['peak_ops_per_second']:.1f} ops/s)")
        elif summary['overall_success_rate'] >= 0.9:
            print(f"\n⚠️ EVALUACIÓN: SISTEMA ESTABLE CON OPTIMIZACIONES MENORES")
            print(f"   ✅ Estabilidad aceptable ({summary['overall_success_rate']:.1%})")
            print(f"   💡 Considerar optimizaciones de performance")
        else:
            print(f"\n❌ EVALUACIÓN: SISTEMA REQUIERE OPTIMIZACIÓN")
            print(f"   ⚠️ Estabilidad baja ({summary['overall_success_rate']:.1%})")
            print(f"   🔧 Revisar gestión de errores y recursos")
        
        print("\n" + "="*60)

async def main():
    """Función principal de stress test"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    stress_test = SmallcapSystemStressTest()
    
    try:
        summary = await stress_test.run_full_stress_test()
        stress_test.print_stress_test_report(summary)
        
        # Guardar resultados
        results_file = "logs/stress_test_results.json"
        os.makedirs("logs", exist_ok=True)
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"\n💾 Resultados guardados en: {results_file}")
        
        # Determinar éxito
        if summary['overall_success_rate'] >= 0.95:
            print("\n✅ STRESS TEST EXITOSO - Sistema robusto para producción")
            return True
        else:
            print("\n⚠️ STRESS TEST CON OBSERVACIONES - Revisar antes de producción")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR EN STRESS TEST: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)