#!/usr/bin/env python3
"""
Launch Daily Plays Scanner on Mac
"""

import subprocess
import webbrowser
import time
import sys
import os

def main():
    print("🚀 Iniciando Daily Plays Scanner...")
    print("📱 URL: http://localhost:8503")
    
    # Cambiar al directorio del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Iniciar streamlit
    try:
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", 
            "web_interface.py", 
            "--server.port", "8503", 
            "--server.headless", "true",
            "--server.address", "localhost"
        ])
        
        # Esperar y abrir navegador
        time.sleep(3)
        webbrowser.open("http://localhost:8503")
        
        print("✅ Scanner iniciado en http://localhost:8503")
        print("🛑 Presiona Ctrl+C para cerrar")
        
        process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Cerrando Scanner...")
        process.terminate()
        process.wait()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()