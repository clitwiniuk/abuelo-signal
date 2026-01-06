#!/bin/bash
# Script para ejecutar el Daily Plays Scanner en puerto específico

echo "🚀 Iniciando Daily Plays Scanner en puerto 8503..."
echo "📱 URL: http://localhost:8503"

streamlit run web_interface.py --server.port 8503 --server.headless true