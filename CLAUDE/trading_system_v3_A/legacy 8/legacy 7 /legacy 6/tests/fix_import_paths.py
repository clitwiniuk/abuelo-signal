#!/usr/bin/env python3
"""
Script para corregir los paths de importación en todos los tests organizados
"""

import os
from pathlib import Path
import re

def fix_import_paths():
    """Corregir paths de importación en todos los tests"""
    base_path = Path(__file__).parent
    
    # Patrones a buscar y reemplazar
    old_pattern = re.compile(
        r"# Agregar el directorio actual al path para importar módulos\n"
        r"current_dir = Path\(__file__\)\.parent\n"
        r"sys\.path\.insert\(0, str\(current_dir\)\)"
    )
    
    new_code = (
        "# Agregar el directorio raíz del proyecto al path para importar módulos\n"
        "project_root = Path(__file__).parent.parent.parent\n"
        "sys.path.insert(0, str(project_root))"
    )
    
    # Buscar todos los archivos Python en subdirectorios
    test_files = []
    for category_dir in base_path.iterdir():
        if category_dir.is_dir() and category_dir.name not in ['__pycache__', '.git', 'misc']:
            for test_file in category_dir.glob('test_*.py'):
                test_files.append(test_file)
    
    print(f"🔧 Corrigiendo paths de importación en {len(test_files)} archivos...")
    
    fixed_count = 0
    for test_file in test_files:
        try:
            # Leer archivo
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Aplicar corrección
            new_content = old_pattern.sub(new_code, content)
            
            # Si hubo cambios, escribir archivo
            if new_content != content:
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                fixed_count += 1
                print(f"   ✅ Corregido: {test_file.relative_to(base_path)}")
        
        except Exception as e:
            print(f"   ❌ Error procesando {test_file.name}: {e}")
    
    print(f"\n📊 Resumen: {fixed_count} archivos corregidos")
    return fixed_count

if __name__ == "__main__":
    fixed_count = fix_import_paths()
    print(f"🏁 Corrección completada: {fixed_count} archivos actualizados")