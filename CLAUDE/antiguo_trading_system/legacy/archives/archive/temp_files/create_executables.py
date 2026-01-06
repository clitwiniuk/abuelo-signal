# create_executables.py
"""
Script para crear ejecutables del sistema de trading
"""

import os
import subprocess
import sys

def create_executable():
    """Crear ejecutables para ambos sistemas"""
    
    print("🚀 Creando ejecutables del sistema de trading...")
    
    # Comandos para crear ejecutables
    commands = [
        {
            'name': 'Trading System',
            'script': 'streamlit_app_v2.py',
            'output': 'TradingSystem',
            'port': '8501',
            'icon': 'assets/trading_icon.ico'  # Si tienes icono
        },
        {
            'name': 'Daily Plays Scanner', 
            'script': 'scanner/web_interface.py',
            'output': 'DailyPlaysScanner',
            'port': '8503',
            'icon': 'assets/scanner_icon.ico'  # Si tienes icono
        }
    ]
    
    for cmd in commands:
        print(f"\n📦 Creando {cmd['name']}...")
        
        # Crear wrapper script
        wrapper_content = f"""
import subprocess
import webbrowser
import time
import sys
import os

def main():
    print("🚀 Iniciando {cmd['name']}...")
    print("📱 URL: http://localhost:{cmd['port']}")
    
    # Cambiar al directorio correcto
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Iniciar streamlit
    process = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", 
        "{cmd['script']}", 
        "--server.port", "{cmd['port']}", 
        "--server.headless", "true"
    ])
    
    # Esperar un poco y abrir navegador
    time.sleep(3)
    webbrowser.open("http://localhost:{cmd['port']}")
    
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\\n🛑 Cerrando {cmd['name']}...")
        process.terminate()

if __name__ == "__main__":
    main()
"""
        
        # Escribir wrapper
        wrapper_file = f"{cmd['output']}_wrapper.py"
        with open(wrapper_file, 'w') as f:
            f.write(wrapper_content)
        
        # Comando PyInstaller
        pyinstaller_cmd = [
            'pyinstaller',
            '--onefile',
            '--windowed',
            '--name', cmd['output']
        ]
        
        # Agregar icono si existe
        if os.path.exists(cmd['icon']):
            pyinstaller_cmd.extend(['--icon', cmd['icon']])
        
        pyinstaller_cmd.append(wrapper_file)
        
        # Ejecutar PyInstaller
        try:
            subprocess.run(pyinstaller_cmd, check=True)
            print(f"✅ {cmd['name']} creado exitosamente!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creando {cmd['name']}: {e}")
        except FileNotFoundError:
            print("❌ PyInstaller no encontrado. Instala con: pip install pyinstaller")
            return
    
    print("\n🎉 ¡Ejecutables creados!")
    print("📁 Los encontrarás en la carpeta 'dist/'")
    print("\n💡 Instrucciones:")
    print("- TradingSystem.exe → Sistema principal (puerto 8501)")
    print("- DailyPlaysScanner.exe → Scanner daily plays (puerto 8503)")

if __name__ == "__main__":
    create_executable()