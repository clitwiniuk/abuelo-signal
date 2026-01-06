#!/bin/bash
# Script para resetear TradeTally sync y resincronizar desde cero

echo "🔄 RESET Y RESINCRONIZACIÓN DE TRADETALLY"
echo "========================================="
echo ""
echo "⚠️  ADVERTENCIA: Este script va a:"
echo "   1. Borrar el archivo de estado de sincronización local"
echo "   2. Marcar todos los trades como NO sincronizados"
echo "   3. NO borrará los trades de TradeTally (debes hacerlo manualmente)"
echo ""
read -p "¿Continuar? (s/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Ss]$ ]]
then
    echo "❌ Cancelado"
    exit 1
fi

# Paso 1: Borrar estado de sincronización
SYNC_STATE_FILE="/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tradetally_sync_state.json"

if [ -f "$SYNC_STATE_FILE" ]; then
    echo "📁 Borrando archivo de estado de sincronización..."
    rm "$SYNC_STATE_FILE"
    echo "✅ Archivo borrado"
else
    echo "ℹ️  No existe archivo de estado previo"
fi

echo ""
echo "📊 SIGUIENTE PASO MANUAL:"
echo "========================"
echo ""
echo "1. Ve a TradeTally y BORRA TODOS LOS TRADES manualmente"
echo "   (o los que quieras resincronizar)"
echo ""
echo "2. Ejecuta el script de sincronización:"
echo "   cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3"
echo "   python3 -m integrations.tradetally.core.tradetally_sync"
echo ""
echo "✅ Reset completado. Listo para resincronizar."
