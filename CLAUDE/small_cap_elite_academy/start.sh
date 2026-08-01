#!/bin/bash

echo "🚀 Iniciando Small Cap Elite Academy..."
echo ""

# Verificar si existe entorno virtual
if [ -d "venv" ]; then
    echo "✅ Activando entorno virtual..."
    source venv/bin/activate
else
    echo "⚠️  No se encontró entorno virtual. Creando uno nuevo..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Inicializar base de datos si no existe
if [ ! -f "database/elite_academy.db" ]; then
    echo "🗄️  Inicializando base de datos..."
    python3 -c "from database.db_manager import init_database; init_database()"
fi

echo ""
echo "🌐 Iniciando aplicación Streamlit..."
echo "📍 La aplicación estará disponible en: http://localhost:8501"
echo ""

streamlit run app.py