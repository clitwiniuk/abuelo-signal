@echo off
echo 🚀 Iniciando Small Cap Elite Academy...
echo.

REM Verificar si existe entorno virtual
if exist "venv\Scripts\activate.bat" (
    echo ✅ Activando entorno virtual...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️  No se encontró entorno virtual. Creando uno nuevo...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
)

REM Inicializar base de datos si no existe
if not exist "database\elite_academy.db" (
    echo 🗄️  Inicializando base de datos...
    python -c "from database.db_manager import init_database; init_database()"
)

echo.
echo 🌐 Iniciando aplicación Streamlit...
echo 📍 La aplicación estará disponible en: http://localhost:8501
echo.

streamlit run app.py

pause