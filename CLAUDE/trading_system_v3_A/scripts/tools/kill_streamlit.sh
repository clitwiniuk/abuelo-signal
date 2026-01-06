#!/bin/bash
# Script para terminar Streamlit de forma forzada

echo "🔍 Buscando procesos Streamlit..."
STREAMLIT_PIDS=$(ps aux | grep streamlit | grep -v grep | awk '{print $2}')

if [ -z "$STREAMLIT_PIDS" ]; then
    echo "❌ No se encontraron procesos Streamlit ejecutándose"
else
    echo "🔫 Terminando procesos Streamlit: $STREAMLIT_PIDS"
    for pid in $STREAMLIT_PIDS; do
        kill -9 $pid 2>/dev/null
        echo "✅ Proceso $pid terminado"
    done
fi

echo "🧹 Limpiando procesos Python relacionados..."
PYTHON_PIDS=$(ps aux | grep python | grep -E "(streamlit|trading)" | grep -v grep | awk '{print $2}')

if [ -n "$PYTHON_PIDS" ]; then
    echo "🔫 Terminando procesos Python: $PYTHON_PIDS"
    for pid in $PYTHON_PIDS; do
        kill -9 $pid 2>/dev/null
        echo "✅ Proceso $pid terminado"
    done
fi

echo "✅ Limpieza completada"