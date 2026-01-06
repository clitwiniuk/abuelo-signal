#!/usr/bin/env python3
"""
ARCHIVO OBSOLETO - DEPRECADO

Este archivo ha sido REEMPLAZADO por el sistema unificado:
- Usar: main.py (que apunta a unified_main.py)
- Backup original en: archive/deprecated/smallcap_production_runner_old.py

PROBLEMAS que causaba este archivo:
❌ IBKRAdapter duplicado (client_id=100 vs client_id=1)
❌ TradingEngine duplicado (ejecuciones conflictivas)
❌ SmallcapMayordomo separado (posiciones no sincronizadas)
❌ TelegramClient duplicado (logs incorrectos)

SOLUCIÓN: Sistema Unificado con Singleton + Service Locator
"""

import sys
import os

print("⚠️  ARCHIVO OBSOLETO")
print("📁 Este archivo ha sido reemplazado por el sistema unificado")
print("🚀 Usa: python main.py")
print("💾 Backup original en: archive/deprecated/smallcap_production_runner_old.py")
print()
print("❌ PROBLEMAS que resuelve el sistema unificado:")
print("   • IBKRAdapter duplicado → Una sola instancia")
print("   • TradingEngine duplicado → Ejecución única")
print("   • Posiciones no sincronizadas → Estado compartido")
print("   • Logs de Telegram incorrectos → Notificaciones unificadas")
print()
sys.exit(1)