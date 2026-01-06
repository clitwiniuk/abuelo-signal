#!/bin/bash
# Script to kill old trader/scanner processes

echo "🔍 Buscando procesos de trading..."
echo ""

# Find trader processes
TRADER_PIDS=$(ps aux | grep "trader_main.py" | grep -v grep | awk '{print $2}')
SCANNER_PIDS=$(ps aux | grep "scanner_main.py" | grep -v grep | awk '{print $2}')

if [ -z "$TRADER_PIDS" ] && [ -z "$SCANNER_PIDS" ]; then
    echo "✅ No hay procesos de trading ejecutándose"
    exit 0
fi

echo "📊 Procesos encontrados:"
echo ""

if [ -n "$TRADER_PIDS" ]; then
    echo "🔹 TRADER processes:"
    ps aux | grep "trader_main.py" | grep -v grep | awk '{printf "   PID %s - Started: %s %s %s\n", $2, $9, $10, $11}'
    echo ""
fi

if [ -n "$SCANNER_PIDS" ]; then
    echo "🔹 SCANNER processes:"
    ps aux | grep "scanner_main.py" | grep -v grep | awk '{printf "   PID %s - Started: %s %s %s\n", $2, $9, $10, $11}'
    echo ""
fi

echo "⚠️  ADVERTENCIA: Se matarán TODOS los procesos listados arriba"
read -p "¿Continuar? (s/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "❌ Cancelado"
    exit 1
fi

# Kill all processes
if [ -n "$TRADER_PIDS" ]; then
    echo "🔪 Matando procesos TRADER..."
    for pid in $TRADER_PIDS; do
        kill $pid 2>/dev/null && echo "   ✅ PID $pid killed" || echo "   ❌ PID $pid ya no existe"
    done
fi

if [ -n "$SCANNER_PIDS" ]; then
    echo "🔪 Matando procesos SCANNER..."
    for pid in $SCANNER_PIDS; do
        kill $pid 2>/dev/null && echo "   ✅ PID $pid killed" || echo "   ❌ PID $pid ya no existe"
    done
fi

sleep 2

# Verify
REMAINING=$(ps aux | grep -E "trader_main|scanner_main" | grep -v grep | wc -l)
if [ "$REMAINING" -eq 0 ]; then
    echo ""
    echo "✅ Todos los procesos han sido detenidos correctamente"
else
    echo ""
    echo "⚠️  Algunos procesos siguen ejecutándose. Ejecuta con -9 para forzar:"
    echo "   kill -9 \$(ps aux | grep -E 'trader_main|scanner_main' | grep -v grep | awk '{print \$2}')"
fi
