#!/usr/bin/env python3
"""
Unified Trading System - SISTEMA PRINCIPAL UNIFICADO

REEMPLAZA los sistemas duplicados:
- main.py anterior → archive/deprecated/main_old.py
- smallcap_production_runner.py → archive/deprecated/

SOLUCIONA DEFINITIVAMENTE:
✅ Una sola instancia IBKRAdapter (no más conflictos client_id)
✅ RiskManager/Mayordomo unificado (posiciones sincronizadas)
✅ TradingEngine único (no más ejecuciones duplicadas)
✅ TelegramClient centralizado (logs unificados)
✅ Configuración única desde config.ini

ARQUITECTURA: Singleton + Service Locator + Dependency Injection
"""

from unified_main import main
import asyncio

if __name__ == "__main__":
    print("🚀 UNIFIED TRADING SYSTEM")
    print("   ✅ Arquitectura unificada")
    print("   ✅ Sin duplicaciones")
    print("   ✅ Posiciones sincronizadas")
    print()
    
    asyncio.run(main())