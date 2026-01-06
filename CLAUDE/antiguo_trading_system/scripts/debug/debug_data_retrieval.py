#!/usr/bin/env python3
"""
Script de diagnóstico para verificar si el problema es del código o del broker
"""

import asyncio
import logging
import sys
from datetime import datetime
from adapters.thread_safe_ibkr_adapter import ThreadSafeIBKRAdapter

# Configurar logging detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_symbol_data_retrieval():
    """Test data retrieval with different symbol categories"""
    
    # Símbolos de prueba en diferentes categorías
    test_symbols = {
        "Blue Chips (Siempre funcionan)": ["AAPL", "MSFT", "GOOGL"],
        "Large Caps Populares": ["TSLA", "NVDA", "META"],
        "Symbols del scanner (problemáticos)": ["ANGH", "CRVO", "CELC", "VAPE", "GTI", "SMX", "MCVT"],
        "Small caps conocidos": ["AMC", "SNDL", "BBBY"]
    }
    
    adapter = None
    results = {}
    
    try:
        # Inicializar adapter
        logger.info("🔧 Inicializando IBKR adapter...")
        adapter = ThreadSafeIBKRAdapter(host="127.0.0.1", port=7497, client_id=999)
        
        # Conectar
        logger.info("🔌 Conectando a IBKR...")
        connected = await adapter.connect()
        if not connected:
            logger.error("❌ No se pudo conectar a IBKR")
            return
        
        logger.info("✅ Conectado a IBKR exitosamente")
        
        # Probar cada categoría de símbolos
        for category, symbols in test_symbols.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"🧪 PROBANDO: {category}")
            logger.info(f"{'='*60}")
            
            results[category] = {}
            
            for symbol in symbols:
                logger.info(f"\n📊 Probando símbolo: {symbol}")
                
                try:
                    # Probar con timeout específico
                    start_time = datetime.now()
                    
                    bars = await asyncio.wait_for(
                        adapter.get_bars(symbol, "1 min", 10),
                        timeout=10.0  # 10 segundos timeout
                    )
                    
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    if bars and len(bars) > 0:
                        latest_bar = bars[-1]
                        results[category][symbol] = {
                            "status": "✅ SUCCESS",
                            "bars_count": len(bars),
                            "latest_timestamp": latest_bar.timestamp,
                            "latest_price": latest_bar.close,
                            "duration_seconds": duration
                        }
                        logger.info(f"✅ {symbol}: {len(bars)} bars, precio actual: ${latest_bar.close}, tiempo: {duration:.1f}s")
                    else:
                        results[category][symbol] = {
                            "status": "⚠️ NO DATA",
                            "bars_count": 0,
                            "duration_seconds": duration
                        }
                        logger.warning(f"⚠️ {symbol}: Sin datos, tiempo: {duration:.1f}s")
                        
                except asyncio.TimeoutError:
                    results[category][symbol] = {
                        "status": "❌ TIMEOUT",
                        "bars_count": 0,
                        "duration_seconds": 10.0
                    }
                    logger.error(f"❌ {symbol}: Timeout después de 10 segundos")
                    
                except Exception as e:
                    error_msg = str(e)
                    if "366" in error_msg or "NO_HISTORICAL_DATA" in error_msg:
                        status = "❌ ERROR 366 (No historical data)"
                    else:
                        status = f"❌ ERROR: {error_msg}"
                    
                    results[category][symbol] = {
                        "status": status,
                        "bars_count": 0,
                        "error": error_msg
                    }
                    logger.error(f"❌ {symbol}: {status}")
                
                # Pequeña pausa entre símbolos para no sobrecargar IBKR
                await asyncio.sleep(1)
        
        # Imprimir resumen detallado
        print_detailed_summary(results)
        
    except Exception as e:
        logger.error(f"Error en prueba general: {e}")
        
    finally:
        if adapter:
            logger.info("🔌 Desconectando...")
            await adapter.disconnect()

def print_detailed_summary(results):
    """Imprimir resumen detallado de resultados"""
    
    print(f"\n{'='*80}")
    print("📋 RESUMEN DETALLADO DE DIAGNÓSTICO")
    print(f"{'='*80}")
    
    total_symbols = 0
    success_count = 0
    timeout_count = 0
    error_366_count = 0
    other_errors = 0
    
    for category, symbols in results.items():
        print(f"\n🔍 {category}:")
        print("-" * 60)
        
        for symbol, data in symbols.items():
            total_symbols += 1
            status = data["status"]
            
            if "SUCCESS" in status:
                success_count += 1
                print(f"  ✅ {symbol:8} | {data['bars_count']:3} bars | ${data.get('latest_price', 'N/A'):>8} | {data['duration_seconds']:.1f}s")
            elif "TIMEOUT" in status:
                timeout_count += 1
                print(f"  ❌ {symbol:8} | TIMEOUT después de {data['duration_seconds']:.1f}s")
            elif "366" in status:
                error_366_count += 1
                print(f"  ❌ {symbol:8} | ERROR 366 (Sin datos históricos)")
            else:
                other_errors += 1
                print(f"  ❌ {symbol:8} | {status}")
    
    # Estadísticas finales
    print(f"\n{'='*80}")
    print("📊 ESTADÍSTICAS FINALES:")
    print(f"{'='*80}")
    print(f"Total símbolos probados: {total_symbols}")
    print(f"✅ Exitosos:            {success_count:3} ({success_count/total_symbols*100:.1f}%)")
    print(f"⏰ Timeouts:            {timeout_count:3} ({timeout_count/total_symbols*100:.1f}%)")
    print(f"📊 Error 366:           {error_366_count:3} ({error_366_count/total_symbols*100:.1f}%)")
    print(f"❌ Otros errores:       {other_errors:3} ({other_errors/total_symbols*100:.1f}%)")
    
    # Diagnóstico
    print(f"\n{'='*80}")
    print("🔍 DIAGNÓSTICO:")
    print(f"{'='*80}")
    
    if success_count == 0:
        print("🚨 ¡PROBLEMA CRÍTICO! Ningún símbolo funciona")
        print("   → Posible problema de conexión o suscripción IBKR")
        print("   → Verifica estado de TWS/Gateway y permisos de datos")
    elif success_count > 0 and success_count < total_symbols // 2:
        print("⚠️  PROBLEMA PARCIAL - Algunos símbolos funcionan")
        print("   → Conexión IBKR OK, pero algunos símbolos sin datos")
        print("   → Símbolos problemáticos pueden ser inválidos/delisted")
    elif success_count >= total_symbols // 2:
        print("✅ SISTEMA MAYORMENTE FUNCIONAL")
        print("   → La mayoría de símbolos funcionan correctamente")
        print("   → Problemas específicos con algunos símbolos del scanner")
    
    if timeout_count > success_count:
        print("⏰ DEMASIADOS TIMEOUTS - Posible problema de red o IBKR")
    
    if error_366_count > 0:
        print(f"📊 {error_366_count} símbolos sin datos históricos (normal para penny stocks)")

async def main():
    """Función principal"""
    print("🔍 DIAGNÓSTICO DE RECUPERACIÓN DE DATOS IBKR")
    print("=" * 80)
    print("Este script probará la recuperación de datos con diferentes tipos de símbolos")
    print("para determinar si el problema es del código o del broker.\n")
    
    # Verificar que TWS/Gateway esté corriendo
    print("📋 REQUISITOS PREVIOS:")
    print("  1. ✅ TWS o IB Gateway debe estar ejecutándose")
    print("  2. ✅ Puerto 7497 debe estar habilitado para API")
    print("  3. ✅ Suscripción de datos debe estar activa")
    print()
    
    response = input("¿Continuar con el diagnóstico? (y/N): ").strip().lower()
    if response != 'y':
        print("Diagnóstico cancelado.")
        return
    
    await test_symbol_data_retrieval()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Diagnóstico interrumpido por el usuario")
    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
        sys.exit(1)