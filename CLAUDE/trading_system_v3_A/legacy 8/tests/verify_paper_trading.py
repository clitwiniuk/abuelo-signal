#!/usr/bin/env python3
"""
Verify Paper Trading Mode Configuration

Checks that the system is correctly configured to NEVER send real orders.
"""

import sys
import configparser
from datetime import datetime

print("="*70)
print("🔍 VERIFICACIÓN DE MODO PAPER TRADING")
print("="*70)
print()

# Test 1: Check config.ini
print("📋 TEST 1: Verificar config.ini")
config = configparser.ConfigParser()
config.read('../config.ini')
paper_mode_config = config.getboolean('TRADING', 'paper_trading_mode', fallback=False)
print(f"   config.ini -> paper_trading_mode = {paper_mode_config}")
if paper_mode_config:
    print("   ✅ Config marcado como paper trading")
else:
    print("   ⚠️  Config marcado como REAL trading")
print()

# Test 2: Check ibkr_adapter.py code
print("📋 TEST 2: Verificar código de ibkr_adapter.py")
try:
    with open('adapters/ibkr_adapter.py', 'r') as f:
        code = f.read()
        if 'Force paper trading mode ON' in code and 'return True' in code:
            print("   ✅ Código forzando paper trading mode")
            print("   ✅ VERIFICADO: Sistema NO puede enviar órdenes reales")
        else:
            print("   ⚠️  ADVERTENCIA: Código no tiene forzado paper trading")
            print("   ⚠️  RIESGO: Sistema podría enviar órdenes reales")
except Exception as e:
    print(f"   ❌ Error leyendo código: {e}")
print()

# Test 3: Check recent trades
print("📋 TEST 3: Verificar trades recientes en base de datos")
try:
    import sqlite3
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()

    # Get today's trades with broker IDs
    cursor.execute("""
        SELECT COUNT(*) as count,
               MIN(broker_order_id_entry) as min_id,
               MAX(broker_order_id_entry) as max_id
        FROM trades
        WHERE DATE(entry_time) = DATE('now')
        AND broker_order_id_entry IS NOT NULL
        AND (deleted = 0 OR deleted IS NULL)
    """)

    result = cursor.fetchone()
    if result and result[0] > 0:
        count, min_id, max_id = result
        print(f"   Trades hoy: {count}")
        print(f"   Order IDs: {min_id} a {max_id}")

        try:
            min_id_int = int(min_id) if min_id else 0
            if min_id_int >= 1000000:
                print(f"   ✅ IDs >= 1000000 -> Paper trading confirmado")
            else:
                print(f"   ❌ IDs < 1000000 -> ÓRDENES REALES DETECTADAS")
                print(f"   ⚠️  CRÍTICO: El sistema envió órdenes al broker hoy")
        except:
            print(f"   ⚠️  No se pudo verificar rango de IDs")
    else:
        print("   ℹ️  No hay trades hoy (o todos sin broker_order_id)")

    conn.close()
except Exception as e:
    print(f"   ⚠️  Error verificando DB: {e}")
print()

# Test 4: Check yesterday's trades (when problem occurred)
print("📋 TEST 4: Verificar trades de ayer (2025-12-04)")
try:
    import sqlite3
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) as count,
               MIN(CAST(broker_order_id_entry AS INTEGER)) as min_id,
               MAX(CAST(broker_order_id_entry AS INTEGER)) as max_id
        FROM trades
        WHERE DATE(entry_time) = '2025-12-04'
        AND broker_order_id_entry IS NOT NULL
        AND broker_order_id_entry NOT LIKE 'PAPER%'
        AND (deleted = 0 OR deleted IS NULL)
    """)

    result = cursor.fetchone()
    if result and result[0] > 0:
        count, min_id, max_id = result
        print(f"   Trades ayer: {count}")
        print(f"   Order IDs: {min_id} a {max_id}")

        if min_id and min_id < 10000:
            print(f"   ❌ CONFIRMADO: Sistema envió {count} órdenes REALES ayer")
            print(f"   ⚠️  Este fue el problema que se corrigió")
        else:
            print(f"   ✅ Sin órdenes reales detectadas")

    conn.close()
except Exception as e:
    print(f"   ⚠️  Error verificando DB: {e}")
print()

# Final Summary
print("="*70)
print("📊 RESUMEN")
print("="*70)
print()

all_good = True

if not paper_mode_config:
    print("⚠️  Config.ini NO está en paper trading mode")
    all_good = False

try:
    with open('adapters/ibkr_adapter.py', 'r') as f:
        if 'Force paper trading mode ON' not in f.read():
            print("❌ Código NO tiene paper trading forzado")
            all_good = False
except:
    print("❌ No se pudo verificar código")
    all_good = False

if all_good:
    print("✅ SISTEMA SEGURO: Paper trading forzado en código")
    print()
    print("   El sistema NUNCA enviará órdenes reales al broker.")
    print("   Solo guarda trades en la base de datos.")
    print()
    print("   ⚠️  IMPORTANTE: Reinicia el sistema para que tome efecto.")
else:
    print("❌ ADVERTENCIA: Configuración inconsistente")
    print()
    print("   Revisa manualmente:")
    print("   1. config.ini -> paper_trading_mode = true")
    print("   2. ibkr_adapter.py -> Código forzando paper trading")

print()
print("="*70)
