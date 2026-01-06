#!/usr/bin/env python3
"""
Script para probar la sincronización de métricas ML con TradeTally
"""

import os
import sys
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3')

from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

def main():
    # Configuración
    API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImY0NTY3M2I2LTUyNjctNGM5OS1hZTI3LTFkOTFhZGY3NjkxZCIsImVtYWlsIjoicmVwcm9wZWw3OEBnbWFpbC5jb20iLCJ1c2VybmFtZSI6InJlcHJvcGVsIiwicm9sZSI6InVzZXIiLCJpYXQiOjE3NTY1MjgxNzUsImV4cCI6MTc1NzEzMjk3NX0.h_7lc8Jufife3d7LxiKrgZu3T2ztzSm-GIofFGVCkb4"
    BASE_URL = "http://localhost:3001/api"
    DB_PATH = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"
    
    print("🚀 Testing ML Metrics Sync with TradeTally...")
    
    # Crear instancia de integración
    sync = TradeTallyIntegration(API_KEY, BASE_URL, DB_PATH)
    
    # Probar conexión
    if not sync.test_connection():
        print("❌ No se pudo conectar con TradeTally")
        return
    
    # Obtener algunos trades para verificar métricas ML
    trades = sync.get_local_trades(only_new=False)  # Get all trades to see ML metrics
    
    if trades:
        print(f"\n📊 Analyzing {len(trades)} trades with ML metrics:")
        
        for i, trade in enumerate(trades[:3]):  # Show first 3 trades
            print(f"\n--- Trade {i+1}: {trade.symbol} ---")
            print(f"Strategy: {trade.strategy}")
            print(f"Confidence: {trade.confidence}%")
            print(f"Strategy Confidence: {trade.strategy_confidence}%")
            print(f"ML Signal Quality: {trade.ml_signal_quality}%")
            print(f"Market Context Score: {trade.market_context_score}%")
            print(f"Trade Session: {trade.trade_session}")
            print(f"Volume Ratio: {trade.volume_ratio}")
            print(f"Gap Percentage: {trade.gap_percentage}")
            print(f"PnL: ${trade.pnl}")
        
        # Test payload creation
        sample_trade = trades[0]
        payload = sync.create_tradetally_payload(sample_trade)
        
        print(f"\n🔍 Sample TradeTally payload:")
        for key, value in payload.items():
            if key.startswith(('strategy', 'ml', 'market', 'trade', 'volume', 'gap')):
                print(f"  {key}: {value}")
    else:
        print("❌ No trades found")

if __name__ == "__main__":
    main()