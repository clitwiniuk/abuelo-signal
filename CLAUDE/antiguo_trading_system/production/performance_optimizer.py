# production/performance_optimizer.py
"""
Optimizador de Performance para Smallcaps Intraday Trading
Aprovecha el sistema híbrido para optimizar latencia, memoria y throughput
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import time
import gc
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import weakref
from functools import wraps

# Aprovechar sistema híbrido
from production.hybrid_config_manager import HybridConfigManager

@dataclass
class PerformanceMetrics:
    """Métricas de performance"""
    operation: str
    start_time: float
    end_time: float
    duration_ms: float
    memory_used_mb: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None

class PerformanceCache:
    """Cache optimizado para datos de trading"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.access_times = {}
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        with self.lock:
            if key not in self.cache:
                return None
            
            # Verificar TTL
            if time.time() - self.access_times[key] > self.ttl_seconds:
                del self.cache[key]
                del self.access_times[key]
                return None
            
            # Actualizar tiempo de acceso
            self.access_times[key] = time.time()
            return self.cache[key]
    
    def set(self, key: str, value: Any):
        """Guardar valor en cache"""
        with self.lock:
            # Limpiar cache si está lleno
            if len(self.cache) >= self.max_size:
                self._evict_oldest()
            
            self.cache[key] = value
            self.access_times[key] = time.time()
    
    def _evict_oldest(self):
        """Eliminar entradas más antiguas"""
        if not self.access_times:
            return
        
        oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[oldest_key]
        del self.access_times[oldest_key]
    
    def clear(self):
        """Limpiar cache"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Estadísticas del cache"""
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hit_ratio": len(self.cache) / max(self.max_size, 1),
                "oldest_entry_age": time.time() - min(self.access_times.values()) if self.access_times else 0
            }

class ConnectionPool:
    """Pool de conexiones optimizado"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.active_connections = []
        self.available_connections = []
        self.lock = threading.Lock()
        self.connection_count = 0
    
    def acquire_connection(self):
        """Adquirir conexión del pool"""
        with self.lock:
            if self.available_connections:
                conn = self.available_connections.pop()
                self.active_connections.append(conn)
                return conn
            
            if self.connection_count < self.max_connections:
                # Simular nueva conexión
                conn_id = f"conn_{self.connection_count}"
                self.connection_count += 1
                self.active_connections.append(conn_id)
                return conn_id
            
            # Pool agotado
            return None
    
    def release_connection(self, connection):
        """Liberar conexión al pool"""
        with self.lock:
            if connection in self.active_connections:
                self.active_connections.remove(connection)
                self.available_connections.append(connection)
    
    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas del pool"""
        with self.lock:
            return {
                "total_connections": self.connection_count,
                "active_connections": len(self.active_connections),
                "available_connections": len(self.available_connections),
                "pool_utilization": len(self.active_connections) / max(self.max_connections, 1)
            }

def performance_monitor(operation_name: str):
    """Decorator para monitorear performance de operaciones"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = _get_memory_usage()
            
            try:
                result = await func(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
                raise
            finally:
                end_time = time.time()
                end_memory = _get_memory_usage()
                
                metrics = PerformanceMetrics(
                    operation=operation_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000,
                    memory_used_mb=end_memory - start_memory,
                    cpu_percent=0,  # Simplificado
                    success=success,
                    error_message=error
                )
                
                # Log si es lento
                if metrics.duration_ms > 1000:  # > 1 segundo
                    logging.getLogger("Performance").warning(
                        f"Operación lenta: {operation_name} tomó {metrics.duration_ms:.1f}ms"
                    )
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = _get_memory_usage()
            
            try:
                result = func(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
                raise
            finally:
                end_time = time.time()
                end_memory = _get_memory_usage()
                
                metrics = PerformanceMetrics(
                    operation=operation_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000,
                    memory_used_mb=end_memory - start_memory,
                    cpu_percent=0,  # Simplificado
                    success=success,
                    error_message=error
                )
                
                # Log si es lento
                if metrics.duration_ms > 1000:
                    logging.getLogger("Performance").warning(
                        f"Operación lenta: {operation_name} tomó {metrics.duration_ms:.1f}ms"
                    )
            
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def _get_memory_usage() -> float:
    """Obtener uso de memoria en MB"""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except:
        return 0.0

class SmallcapPerformanceOptimizer:
    """
    Optimizador de performance para sistema smallcaps intraday
    Integra con HybridConfigManager para configuración optimizada
    """
    
    def __init__(self):
        self.logger = logging.getLogger("PerformanceOptimizer")
        
        # Cargar configuración híbrida
        try:
            self.hybrid_config = HybridConfigManager()
            self.config = self._load_optimization_config()
            self.logger.info("✅ Configuración híbrida cargada para optimización")
        except Exception as e:
            self.logger.error(f"❌ Error cargando configuración: {e}")
            raise
        
        # Componentes de optimización
        self.cache = PerformanceCache(
            max_size=self.config["cache"]["max_size"],
            ttl_seconds=self.config["cache"]["ttl_seconds"]
        )
        
        self.connection_pool = ConnectionPool(
            max_connections=self.config["connection_pool"]["max_connections"]
        )
        
        # Métricas de performance
        self.performance_history = []
        self.optimization_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "operations_optimized": 0,
            "memory_cleanups": 0,
            "connection_reuses": 0
        }
        
        # Threading
        self.executor = ThreadPoolExecutor(
            max_workers=self.config["threading"]["max_workers"]
        )
        
    def _load_optimization_config(self) -> Dict[str, Any]:
        """Cargar configuración de optimización"""
        try:
            complete_config = self.hybrid_config.get_complete_hybrid_config()
            production_ext = complete_config["production_extensions"]
            
            # Usar configuración de performance desde config.ini si existe
            base_config = complete_config["base_config"]
            performance_config = base_config.get("performance_optimization", {})
            
            return {
                "cache": {
                    "max_size": int(performance_config.get("max_signals_history", "1000")),
                    "ttl_seconds": int(performance_config.get("memory_cleanup_interval", "300")),
                    "enabled": performance_config.get("batch_processing_enabled", "true").lower() == "true"
                },
                
                "connection_pool": {
                    "max_connections": int(base_config.get("connection_pool", {}).get("max_connections", "5")),
                    "timeout_seconds": float(base_config.get("connection_pool", {}).get("connection_timeout", "60.0")),
                    "enabled": performance_config.get("connection_pool_enabled", "true").lower() == "true"
                },
                
                "threading": {
                    "max_workers": 10,
                    "batch_size": 50
                },
                
                "memory": {
                    "cleanup_interval": int(performance_config.get("memory_cleanup_interval", "300")),
                    "max_memory_mb": 512,
                    "gc_threshold": 0.8
                },
                
                "rate_limiting": base_config.get("rate_limiting", {}),
                
                "smallcap_optimizations": {
                    "preload_symbols": True,
                    "batch_market_data": True,
                    "cache_technical_indicators": True,
                    "parallel_scanning": True
                }
            }
        except Exception as e:
            self.logger.error(f"Error en configuración optimización: {e}")
            # Configuración fallback
            return {
                "cache": {"max_size": 1000, "ttl_seconds": 300, "enabled": True},
                "connection_pool": {"max_connections": 5, "timeout_seconds": 60.0, "enabled": True},
                "threading": {"max_workers": 10, "batch_size": 50},
                "memory": {"cleanup_interval": 300, "max_memory_mb": 512, "gc_threshold": 0.8},
                "smallcap_optimizations": {
                    "preload_symbols": True,
                    "batch_market_data": True,
                    "cache_technical_indicators": True,
                    "parallel_scanning": True
                }
            }
    
    @performance_monitor("symbol_data_fetch")
    async def optimized_symbol_fetch(self, symbols: List[str]) -> Dict[str, Any]:
        """Fetch optimizado de datos de símbolos con cache y batching"""
        results = {}
        cache_hits = 0
        cache_misses = 0
        
        # 1. Verificar cache primero
        uncached_symbols = []
        for symbol in symbols:
            cache_key = f"symbol_data_{symbol}"
            cached_data = self.cache.get(cache_key)
            
            if cached_data:
                results[symbol] = cached_data
                cache_hits += 1
                self.optimization_stats["cache_hits"] += 1
            else:
                uncached_symbols.append(symbol)
                cache_misses += 1
                self.optimization_stats["cache_misses"] += 1
        
        # 2. Fetch en paralelo solo símbolos no cacheados
        if uncached_symbols:
            batch_size = self.config["threading"]["batch_size"]
            
            # Dividir en batches para optimizar
            for i in range(0, len(uncached_symbols), batch_size):
                batch = uncached_symbols[i:i + batch_size]
                
                # Simular fetch en paralelo
                batch_results = await self._fetch_symbol_batch(batch)
                
                # Guardar en cache y resultados
                for symbol, data in batch_results.items():
                    cache_key = f"symbol_data_{symbol}"
                    self.cache.set(cache_key, data)
                    results[symbol] = data
        
        self.logger.debug(f"Symbol fetch: {cache_hits} hits, {cache_misses} misses")
        return results
    
    async def _fetch_symbol_batch(self, symbols: List[str]) -> Dict[str, Any]:
        """Simular fetch de batch de símbolos"""
        # En implementación real, aquí iría la lógica de IBKR/Tiingo
        await asyncio.sleep(0.01)  # Simular latencia de API
        
        return {
            symbol: {
                "price": 5.0 + hash(symbol) % 10,  # Price simulado
                "volume": 100000 + hash(symbol) % 500000,
                "gap": (hash(symbol) % 20) / 100,
                "timestamp": datetime.now().isoformat()
            }
            for symbol in symbols
        }
    
    @performance_monitor("technical_analysis")
    async def optimized_technical_analysis(self, symbol: str, bars_data: List[Dict]) -> Dict[str, Any]:
        """Análisis técnico optimizado con cache"""
        cache_key = f"technical_{symbol}_{len(bars_data)}"
        
        # Verificar cache
        cached_result = self.cache.get(cache_key)
        if cached_result and self.config["smallcap_optimizations"]["cache_technical_indicators"]:
            self.optimization_stats["cache_hits"] += 1
            return cached_result
        
        # Calcular indicadores técnicos
        result = await self._calculate_technical_indicators(symbol, bars_data)
        
        # Guardar en cache
        self.cache.set(cache_key, result)
        self.optimization_stats["cache_misses"] += 1
        
        return result
    
    async def _calculate_technical_indicators(self, symbol: str, bars_data: List[Dict]) -> Dict[str, Any]:
        """Calcular indicadores técnicos"""
        # Simular cálculos pesados
        await asyncio.sleep(0.005)
        
        # En implementación real, aquí irían cálculos de RSI, MACD, etc.
        return {
            "rsi": 50.0 + (hash(symbol) % 40),
            "macd": {"signal": 0.1, "histogram": 0.05},
            "ema_9": 5.2,
            "ema_21": 5.1,
            "volume_sma": 150000,
            "calculated_at": datetime.now().isoformat()
        }
    
    @performance_monitor("parallel_scanning")
    async def optimized_market_scan(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Scanning optimizado del mercado en paralelo"""
        if not self.config["smallcap_optimizations"]["parallel_scanning"]:
            # Scanning secuencial (fallback)
            return await self._sequential_scan(symbols)
        
        # Scanning en paralelo
        batch_size = self.config["threading"]["batch_size"]
        batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
        
        all_results = []
        
        # Procesar batches en paralelo
        tasks = [self._scan_symbol_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, Exception):
                self.logger.error(f"Error en batch scanning: {result}")
                continue
            all_results.extend(result)
        
        # Filtrar y ordenar resultados
        filtered_results = self._filter_smallcap_results(all_results)
        
        self.optimization_stats["operations_optimized"] += 1
        return filtered_results
    
    async def _scan_symbol_batch(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Escanear batch de símbolos"""
        results = []
        
        # Obtener datos de mercado optimizado
        market_data = await self.optimized_symbol_fetch(symbols)
        
        for symbol in symbols:
            if symbol not in market_data:
                continue
            
            data = market_data[symbol]
            
            # Simular análisis de smallcap criteria
            criteria_met = self._evaluate_smallcap_criteria(symbol, data)
            
            if criteria_met["passes_filters"]:
                results.append({
                    "symbol": symbol,
                    "price": data["price"],
                    "volume": data["volume"],
                    "gap_percentage": data["gap"],
                    "quality_score": criteria_met["quality_score"],
                    "timestamp": data["timestamp"]
                })
        
        return results
    
    def _evaluate_smallcap_criteria(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluar criterios smallcap"""
        try:
            smallcap_config = self.hybrid_config.get_smallcap_strategy_config()
            
            # Verificar filtros desde config.ini
            price_ok = smallcap_config["min_price"] <= data["price"] <= smallcap_config["max_price"]
            volume_ok = data["volume"] >= smallcap_config["min_volume"]
            gap_ok = data["gap"] >= smallcap_config["min_gap_percent"] / 100
            
            passes_filters = price_ok and volume_ok and gap_ok
            
            # Calcular quality score
            quality_score = 0.0
            if price_ok:
                quality_score += 3.0
            if volume_ok:
                quality_score += 4.0
            if gap_ok:
                quality_score += 3.0
            
            return {
                "passes_filters": passes_filters,
                "quality_score": quality_score,
                "criteria": {
                    "price_ok": price_ok,
                    "volume_ok": volume_ok,
                    "gap_ok": gap_ok
                }
            }
        except Exception as e:
            self.logger.error(f"Error evaluating criteria for {symbol}: {e}")
            return {"passes_filters": False, "quality_score": 0.0}
    
    def _filter_smallcap_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtrar y ordenar resultados de smallcaps"""
        # Filtrar por quality score mínimo
        min_quality = 6.0
        filtered = [r for r in results if r.get("quality_score", 0) >= min_quality]
        
        # Ordenar por quality score descendente
        filtered.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        
        # Limitar a top 20 para performance
        return filtered[:20]
    
    async def _sequential_scan(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Scanning secuencial (fallback)"""
        results = []
        
        for symbol in symbols:
            try:
                market_data = await self.optimized_symbol_fetch([symbol])
                if symbol in market_data:
                    data = market_data[symbol]
                    criteria_met = self._evaluate_smallcap_criteria(symbol, data)
                    
                    if criteria_met["passes_filters"]:
                        results.append({
                            "symbol": symbol,
                            "price": data["price"],
                            "volume": data["volume"],
                            "gap_percentage": data["gap"],
                            "quality_score": criteria_met["quality_score"],
                            "timestamp": data["timestamp"]
                        })
            except Exception as e:
                self.logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        return self._filter_smallcap_results(results)
    
    def optimize_memory_usage(self):
        """Optimizar uso de memoria"""
        try:
            # Limpiar cache si está muy lleno
            cache_stats = self.cache.stats()
            if cache_stats["hit_ratio"] > self.config["memory"]["gc_threshold"]:
                old_size = cache_stats["size"]
                self.cache.clear()
                self.optimization_stats["memory_cleanups"] += 1
                self.logger.info(f"Cache limpiado: {old_size} → 0 entradas")
            
            # Ejecutar garbage collection
            collected = gc.collect()
            if collected > 0:
                self.logger.debug(f"Garbage collection: {collected} objetos liberados")
            
            # Limpiar historial de performance si está muy grande
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-500:]
                
        except Exception as e:
            self.logger.error(f"Error en optimización de memoria: {e}")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de optimización"""
        cache_stats = self.cache.stats()
        pool_stats = self.connection_pool.get_stats()
        
        total_cache_requests = self.optimization_stats["cache_hits"] + self.optimization_stats["cache_misses"]
        cache_hit_rate = (self.optimization_stats["cache_hits"] / max(total_cache_requests, 1)) * 100
        
        return {
            "cache": {
                "hit_rate_percent": cache_hit_rate,
                "total_hits": self.optimization_stats["cache_hits"],
                "total_misses": self.optimization_stats["cache_misses"],
                "current_size": cache_stats["size"],
                "max_size": cache_stats["max_size"]
            },
            "connection_pool": {
                "utilization_percent": pool_stats["pool_utilization"] * 100,
                "active_connections": pool_stats["active_connections"],
                "total_connections": pool_stats["total_connections"],
                "reuses": self.optimization_stats["connection_reuses"]
            },
            "operations": {
                "optimized_operations": self.optimization_stats["operations_optimized"],
                "memory_cleanups": self.optimization_stats["memory_cleanups"]
            },
            "performance": {
                "avg_scan_time_ms": self._calculate_avg_scan_time(),
                "operations_per_second": self._calculate_ops_per_second()
            }
        }
    
    def _calculate_avg_scan_time(self) -> float:
        """Calcular tiempo promedio de scanning"""
        scan_metrics = [m for m in self.performance_history if "scan" in m.operation]
        if not scan_metrics:
            return 0.0
        
        return sum(m.duration_ms for m in scan_metrics) / len(scan_metrics)
    
    def _calculate_ops_per_second(self) -> float:
        """Calcular operaciones por segundo"""
        if len(self.performance_history) < 2:
            return 0.0
        
        time_span = self.performance_history[-1].end_time - self.performance_history[0].start_time
        return len(self.performance_history) / max(time_span, 1)
    
    async def run_optimization_benchmark(self) -> Dict[str, Any]:
        """Ejecutar benchmark de optimización"""
        self.logger.info("🚀 INICIANDO BENCHMARK DE OPTIMIZACIÓN")
        
        # Test symbols
        test_symbols = [f"TEST{i:03d}" for i in range(1, 101)]  # 100 símbolos
        
        benchmark_results = {}
        
        # 1. Test de cache performance
        self.logger.info("📊 Test 1: Cache Performance")
        start_time = time.time()
        
        # Primera pasada (cache miss)
        await self.optimized_symbol_fetch(test_symbols[:20])
        miss_time = time.time() - start_time
        
        # Segunda pasada (cache hit)
        start_time = time.time()
        await self.optimized_symbol_fetch(test_symbols[:20])
        hit_time = time.time() - start_time
        
        benchmark_results["cache_performance"] = {
            "cache_miss_time_ms": miss_time * 1000,
            "cache_hit_time_ms": hit_time * 1000,
            "speedup_factor": miss_time / max(hit_time, 0.001)
        }
        
        # 2. Test de scanning paralelo vs secuencial
        self.logger.info("📊 Test 2: Parallel vs Sequential Scanning")
        
        # Parallel scanning
        start_time = time.time()
        parallel_results = await self.optimized_market_scan(test_symbols[:50])
        parallel_time = time.time() - start_time
        
        # Sequential scanning (simulated)
        start_time = time.time()
        sequential_results = await self._sequential_scan(test_symbols[:10])  # Menos símbolos para evitar timeout
        sequential_time = time.time() - start_time
        sequential_time_extrapolated = sequential_time * 5  # Extrapolar a 50 símbolos
        
        benchmark_results["scanning_performance"] = {
            "parallel_time_ms": parallel_time * 1000,
            "sequential_time_ms": sequential_time_extrapolated * 1000,
            "parallel_results_count": len(parallel_results),
            "sequential_results_count": len(sequential_results) * 5,
            "speedup_factor": sequential_time_extrapolated / max(parallel_time, 0.001)
        }
        
        # 3. Test de memory optimization
        self.logger.info("📊 Test 3: Memory Optimization")
        memory_before = _get_memory_usage()
        
        # Llenar cache
        for i in range(100):
            self.cache.set(f"test_key_{i}", {"data": "x" * 1000})
        
        memory_after_fill = _get_memory_usage()
        
        # Optimizar memoria
        self.optimize_memory_usage()
        memory_after_optimization = _get_memory_usage()
        
        benchmark_results["memory_optimization"] = {
            "memory_before_mb": memory_before,
            "memory_after_fill_mb": memory_after_fill,
            "memory_after_optimization_mb": memory_after_optimization,
            "memory_saved_mb": memory_after_fill - memory_after_optimization
        }
        
        # 4. Estadísticas generales
        optimization_stats = self.get_optimization_stats()
        benchmark_results["optimization_stats"] = optimization_stats
        
        total_benchmark_time = sum([
            benchmark_results["cache_performance"]["cache_miss_time_ms"],
            benchmark_results["cache_performance"]["cache_hit_time_ms"],
            benchmark_results["scanning_performance"]["parallel_time_ms"]
        ]) / 1000
        
        benchmark_results["summary"] = {
            "total_benchmark_time_seconds": total_benchmark_time,
            "overall_performance_score": self._calculate_performance_score(benchmark_results),
            "optimization_recommendations": self._generate_optimization_recommendations(benchmark_results)
        }
        
        return benchmark_results
    
    def _calculate_performance_score(self, results: Dict[str, Any]) -> float:
        """Calcular score de performance general"""
        score = 100.0
        
        # Penalizar por tiempos lentos
        cache_speedup = results["cache_performance"]["speedup_factor"]
        if cache_speedup < 2.0:
            score -= 10
        
        parallel_speedup = results["scanning_performance"]["speedup_factor"]
        if parallel_speedup < 2.0:
            score -= 15
        
        # Bonus por optimizaciones efectivas
        cache_hit_rate = results["optimization_stats"]["cache"]["hit_rate_percent"]
        if cache_hit_rate > 80:
            score += 10
        
        memory_saved = results["memory_optimization"]["memory_saved_mb"]
        if memory_saved > 10:
            score += 5
        
        return max(0, min(100, score))
    
    def _generate_optimization_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generar recomendaciones de optimización"""
        recommendations = []
        
        cache_hit_rate = results["optimization_stats"]["cache"]["hit_rate_percent"]
        if cache_hit_rate < 70:
            recommendations.append("Aumentar tamaño del cache para mejorar hit rate")
        
        parallel_speedup = results["scanning_performance"]["speedup_factor"]
        if parallel_speedup < 2.0:
            recommendations.append("Optimizar paralelización del scanning")
        
        pool_utilization = results["optimization_stats"]["connection_pool"]["utilization_percent"]
        if pool_utilization > 90:
            recommendations.append("Aumentar tamaño del connection pool")
        
        if not recommendations:
            recommendations.append("Sistema bien optimizado - continuar monitoreo")
        
        return recommendations
    
    def print_optimization_report(self, results: Dict[str, Any]):
        """Imprimir reporte de optimización"""
        print("\n" + "="*60)
        print("⚡ REPORTE DE OPTIMIZACIÓN - SMALLCAPS INTRADAY")
        print("="*60)
        
        print(f"\n📊 PERFORMANCE SCORE: {results['summary']['overall_performance_score']:.1f}/100")
        
        # Cache performance
        cache = results["cache_performance"]
        print(f"\n💾 CACHE PERFORMANCE:")
        print(f"   Cache miss: {cache['cache_miss_time_ms']:.1f}ms")
        print(f"   Cache hit: {cache['cache_hit_time_ms']:.1f}ms")
        print(f"   Speedup: {cache['speedup_factor']:.1f}x")
        
        # Scanning performance
        scanning = results["scanning_performance"]
        print(f"\n🔍 SCANNING PERFORMANCE:")
        print(f"   Parallel: {scanning['parallel_time_ms']:.1f}ms ({scanning['parallel_results_count']} results)")
        print(f"   Sequential: {scanning['sequential_time_ms']:.1f}ms (extrapolado)")
        print(f"   Speedup: {scanning['speedup_factor']:.1f}x")
        
        # Memory optimization
        memory = results["memory_optimization"]
        print(f"\n🧠 MEMORY OPTIMIZATION:")
        print(f"   Antes: {memory['memory_before_mb']:.1f}MB")
        print(f"   Después de llenar: {memory['memory_after_fill_mb']:.1f}MB")
        print(f"   Después de optimizar: {memory['memory_after_optimization_mb']:.1f}MB")
        print(f"   Memoria liberada: {memory['memory_saved_mb']:.1f}MB")
        
        # Stats generales
        stats = results["optimization_stats"]
        print(f"\n📈 ESTADÍSTICAS:")
        print(f"   Cache hit rate: {stats['cache']['hit_rate_percent']:.1f}%")
        print(f"   Pool utilization: {stats['connection_pool']['utilization_percent']:.1f}%")
        print(f"   Ops/segundo: {stats['performance']['operations_per_second']:.1f}")
        
        # Recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        for rec in results["summary"]["optimization_recommendations"]:
            print(f"   • {rec}")
        
        print("\n" + "="*60)

async def main():
    """Demo del optimizador de performance"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    optimizer = SmallcapPerformanceOptimizer()
    
    try:
        print("⚡ DEMO OPTIMIZADOR DE PERFORMANCE SMALLCAPS")
        print("=" * 60)
        print("Ejecutando benchmark completo...\n")
        
        # Ejecutar benchmark
        results = await optimizer.run_optimization_benchmark()
        
        # Mostrar reporte
        optimizer.print_optimization_report(results)
        
        # Guardar resultados
        os.makedirs("logs", exist_ok=True)
        with open("logs/performance_benchmark.json", 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Resultados guardados en: logs/performance_benchmark.json")
        
        # Evaluar éxito
        score = results["summary"]["overall_performance_score"]
        if score >= 80:
            print("\n✅ SISTEMA ALTAMENTE OPTIMIZADO")
            return True
        elif score >= 60:
            print("\n⚠️ SISTEMA MODERADAMENTE OPTIMIZADO")
            return True
        else:
            print("\n❌ SISTEMA REQUIERE OPTIMIZACIÓN")
            return False
            
    except Exception as e:
        print(f"\n❌ Error en benchmark: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)