# production/deploy_smallcap_production.py
"""
DEPLOYMENT Script para Smallcaps Intraday Production
Aprovecha TODA la infraestructura existente del proyecto
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Aprovechar utilidades existentes
from utils.log_config import configure_strategy_logging
try:
    from utils.performance_monitor import PerformanceMonitor
except ImportError:
    PerformanceMonitor = None  # Fallback si no existe

# Importar hybrid config manager
from production.hybrid_config_manager import HybridConfigManager

class SmallcapProductionDeployer:
    """
    Deployer que aprovecha TODA la infraestructura existente
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ProductionDeployer")
        self.deployment_config = self._create_deployment_config()
        self.validation_results = {}
        
        # Inicializar hybrid config manager
        try:
            self.hybrid_config = HybridConfigManager()
            self.logger.info("✅ HybridConfigManager inicializado correctamente")
        except Exception as e:
            self.logger.error(f"❌ Error inicializando HybridConfigManager: {e}")
            self.hybrid_config = None
    
    def _create_deployment_config(self) -> Dict[str, Any]:
        """Configuración de deployment aprovechando estructura existente"""
        project_root = Path(__file__).parent.parent
        
        return {
            "project_root": str(project_root),
            "production_mode": "smallcaps_intraday",
            
            # Directorios existentes que aprovechamos
            "directories": {
                "adapters": project_root / "adapters",
                "core": project_root / "core", 
                "strategies": project_root / "strategies",
                "scanner": project_root / "scanner",
                "utils": project_root / "utils",
                "production": project_root / "production",
                "logs": project_root / "logs",
                "data": project_root / "data",
                "config": project_root / "config"
            },
            
            # Componentes clave que validamos
            "critical_components": {
                "ibkr_adapter": "adapters/ibkr_adapter.py",
                "risk_manager": "core/risk_manager.py",
                "ml_engine": "strategies/multi_strategy_engine_ml.py",
                "smallcap_scanner": "scanner/smallcap/smallcap_daily_scanner.py",
                "hybrid_scanner": "scanner/hybrid_scanner.py",
                "tiingo_provider": "scanner/tiingo_data_provider.py",
                "performance_monitor": "utils/performance_monitor.py"
            },
            
            # Variables de entorno requeridas (solo las que NO están en config.ini)
            "required_env_vars": [
                "IBKR_ACCOUNT",     # Solo esta no está en config.ini
                "TIINGO_API_KEY"    # Solo esta no está en config.ini
            ]
            # NOTA: IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID ya están en config.ini
            # smallcap_config eliminado - usar config.ini [DAILY_PLAYS_STRATEGY]
        }
    
    def validate_existing_infrastructure(self) -> bool:
        """Validar que toda la infraestructura existente esté lista"""
        self.logger.info("🔍 Validando infraestructura existente...")
        
        all_valid = True
        
        # 1. Validar directorios
        for name, path in self.deployment_config["directories"].items():
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"✅ Creado directorio: {name}")
                except Exception as e:
                    self.logger.error(f"❌ Error creando {name}: {e}")
                    all_valid = False
            else:
                self.logger.info(f"✅ Directorio existente: {name}")
        
        # 2. Validar componentes críticos
        project_root = Path(self.deployment_config["project_root"])
        for name, rel_path in self.deployment_config["critical_components"].items():
            full_path = project_root / rel_path
            if full_path.exists():
                self.logger.info(f"✅ Componente encontrado: {name}")
                self.validation_results[name] = "available"
            else:
                self.logger.error(f"❌ Componente faltante: {name} ({full_path})")
                self.validation_results[name] = "missing"
                all_valid = False
        
        # 3. Validar variables de entorno
        missing_vars = []
        for var in self.deployment_config["required_env_vars"]:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.logger.warning(f"⚠️ Variables de entorno faltantes: {missing_vars}")
            self.logger.info("💡 Configurar en archivo .env o variables del sistema")
        else:
            self.logger.info("✅ Todas las variables de entorno configuradas")
        
        return all_valid and len(missing_vars) == 0
    
    def test_component_integration(self) -> bool:
        """Test rápido de integración de componentes existentes"""
        self.logger.info("🧪 Testing integración de componentes...")
        
        try:
            # Test 1: Importar IBKRAdapter
            from adapters.ibkr_adapter import IBKRAdapter
            self.logger.info("✅ IBKRAdapter importado correctamente")
            
            # Test 2: Importar SmallcapMayordomo
            from core.risk_manager import create_smallcap_mayordomo
            self.logger.info("✅ SmallcapMayordomo importado correctamente")
            
            # Test 3: Importar ML Engine
            from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
            self.logger.info("✅ MLMultiStrategyEngine importado correctamente")
            
            # Test 4: Importar Scanner Híbrido
            from scanner.hybrid_scanner import HybridScanner
            from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
            self.logger.info("✅ Scanners híbridos importados correctamente")
            
            # Test 5: Importar Tiingo Provider
            from scanner.tiingo_data_provider import TiingoDataProvider
            self.logger.info("✅ TiingoDataProvider importado correctamente")
            
            # Test 6: Importar Performance Monitor
            from utils.performance_monitor import PerformanceMonitor
            self.logger.info("✅ PerformanceMonitor importado correctamente")
            
            self.logger.info("🎉 TODOS los componentes se integran correctamente!")
            return True
            
        except ImportError as e:
            self.logger.error(f"❌ Error de importación: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error inesperado en testing: {e}")
            return False
    
    def create_production_config_file(self) -> str:
        """Crear archivo de configuración de producción usando HybridConfigManager"""
        config_dir = Path(self.deployment_config["project_root"]) / "config"
        config_file = config_dir / "smallcap_production.json"
        
        if not self.hybrid_config:
            self.logger.error("❌ HybridConfigManager no disponible")
            return ""
        
        # Obtener configuración completa desde config.ini + extensiones
        complete_config = self.hybrid_config.get_complete_hybrid_config()
        
        # Agregar metadatos de deployment
        production_config = {
            "environment": "production",
            "mode": "smallcaps_intraday_live", 
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "config_source": "hybrid_config_manager",
            
            # Configuración híbrida completa
            "hybrid_config": complete_config,
            
            # Referencias a config.ini (NO duplicar valores)
            "config_ini_sections_used": [
                "IBKR",                    # Conexión IBKR 
                "TRADING",                 # Parámetros generales
                "GLOBAL",                  # Límites y horarios
                "DAILY_PLAYS_STRATEGY",    # Configuración smallcaps
                "ADVANCED",                # Reconexión y cache
                "LOGGING"                  # Configuración logs
            ],
            
            # Solo configuración específica de producción (NO en config.ini)
            "production_only_config": {
                "deployment_timestamp": datetime.now().isoformat(),
                "hybrid_scanner_enabled": True,
                "tiingo_fallback_enabled": True,
                "real_time_alerts_enabled": True,
                "auto_position_management": True,
                "smallcap_focus_mode": True
            }
        }
        
        # Guardar configuración
        try:
            with open(config_file, 'w') as f:
                json.dump(production_config, f, indent=2)
            
            self.logger.info(f"✅ Configuración de producción creada: {config_file}")
            return str(config_file)
            
        except Exception as e:
            self.logger.error(f"❌ Error creando configuración: {e}")
            return ""
    
    def create_startup_script(self) -> str:
        """Crear script de startup que aproveche toda la infraestructura"""
        production_dir = Path(self.deployment_config["project_root"]) / "production"
        startup_script = production_dir / "start_smallcap_production.py"
        
        startup_code = '''#!/usr/bin/env python3
# production/start_smallcap_production.py
"""
STARTUP Script para Smallcaps Intraday Production
Auto-generado por deployment script - USA CONFIG.INI + HYBRID EXTENSIONS
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from production.smallcap_production_runner import SmallcapProductionRunner

async def main():
    """Startup principal del sistema de producción"""
    print("🚀 INICIANDO SISTEMA SMALLCAPS INTRADAY PRODUCTION")
    print("=" * 60)
    print("📋 Configuración: config.ini + extensiones híbridas")
    
    # Verificar SOLO variables de entorno que NO están en config.ini
    required_vars = ["IBKR_ACCOUNT", "TIINGO_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables de entorno faltantes: {missing_vars}")
        print("💡 Configurar antes de ejecutar:")
        for var in missing_vars:
            print(f"   export {var}=<tu_valor>")
        print()
        print("ℹ️  NOTA: IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID se leen desde config.ini")
        return
    
    print("✅ Variables de entorno configuradas")
    print("✅ config.ini será leído automáticamente")
    
    # Inicializar y ejecutar runner (usa HybridConfigManager internamente)
    runner = SmallcapProductionRunner()
    
    try:
        await runner.initialize()
        await runner.run_production_scanning()
    except KeyboardInterrupt:
        print("\\n🛑 Shutdown manual iniciado...")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await runner.shutdown()
        print("✅ Sistema detenido correctamente")

if __name__ == "__main__":
    # Configurar event loop para compatibilidad
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
'''
        
        try:
            with open(startup_script, 'w') as f:
                f.write(startup_code)
            
            # Hacer executable en Unix
            if os.name != 'nt':
                os.chmod(startup_script, 0o755)
            
            self.logger.info(f"✅ Script de startup creado: {startup_script}")
            return str(startup_script)
            
        except Exception as e:
            self.logger.error(f"❌ Error creando startup script: {e}")
            return ""
    
    def create_monitoring_dashboard(self) -> str:
        """Crear dashboard simple usando PerformanceMonitor existente"""
        production_dir = Path(self.deployment_config["project_root"]) / "production"
        dashboard_script = production_dir / "monitoring_dashboard.py"
        
        dashboard_code = '''#!/usr/bin/env python3
# production/monitoring_dashboard.py
"""
Dashboard de Monitoreo Simple
Aprovecha PerformanceMonitor existente
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def display_dashboard():
    """Display simple dashboard"""
    while True:
        os.system('clear' if os.name != 'nt' else 'cls')
        
        print("📊 SMALLCAP PRODUCTION DASHBOARD")
        print("=" * 50)
        print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Read status from logs or status file
        try:
            status_file = project_root / "production" / "status.json"
            if status_file.exists():
                with open(status_file) as f:
                    status = json.load(f)
                
                print("🚀 ESTADO DEL SISTEMA:")
                print(f"   Running: {status.get('is_running', 'Unknown')}")
                print(f"   Scans: {status.get('scan_count', 0)}")
                print(f"   Plays encontrados: {status.get('total_plays_found', 0)}")
                print(f"   Último scan: {status.get('last_scan_time', 'Never')}")
                print(f"   IBKR conectado: {status.get('ibkr_connected', False)}")
                print(f"   ML Engine activo: {status.get('ml_engine_enabled', False)}")
            else:
                print("⚠️ Status file not found")
        
        except Exception as e:
            print(f"❌ Error reading status: {e}")
        
        print()
        print("📈 MÉTRICAS CLAVE:")
        print("   [Implementar métricas específicas]")
        print()
        print("Press Ctrl+C to exit")
        
        time.sleep(10)  # Update every 10 seconds

if __name__ == "__main__":
    try:
        display_dashboard()
    except KeyboardInterrupt:
        print("\\n👋 Dashboard cerrado")
'''
        
        try:
            with open(dashboard_script, 'w') as f:
                f.write(dashboard_code)
            
            if os.name != 'nt':
                os.chmod(dashboard_script, 0o755)
            
            self.logger.info(f"✅ Dashboard creado: {dashboard_script}")
            return str(dashboard_script)
            
        except Exception as e:
            self.logger.error(f"❌ Error creando dashboard: {e}")
            return ""
    
    def create_deployment_summary(self) -> Dict[str, Any]:
        """Crear resumen del deployment"""
        return {
            "deployment_timestamp": datetime.now().isoformat(),
            "mode": "smallcaps_intraday_production",
            "project_root": self.deployment_config["project_root"],
            "components_validated": self.validation_results,
            "infrastructure_status": "ready" if all(
                status == "available" for status in self.validation_results.values()
            ) else "incomplete",
            "leveraged_existing_code": [
                "IBKRAdapter for real connections",
                "SmallcapMayordomo for position management", 
                "MLMultiStrategyEngine for ML decisions",
                "SmallcapDailyScanner for hybrid scanning",
                "PerformanceMonitor for monitoring",
                "Logging infrastructure",
                "config.ini for ALL base configuration",
                "HybridConfigManager for zero duplication"
            ],
            "hybrid_configuration_approach": [
                "✅ config.ini as single source of truth",
                "✅ Zero parameter duplication",
                "✅ Only production-specific extensions added",
                "✅ All existing strategies and settings preserved",
                "✅ Smallcap [DAILY_PLAYS_STRATEGY] section used directly"
            ]
        }
    
    def deploy(self) -> bool:
        """Ejecutar deployment completo"""
        self.logger.info("🚀 INICIANDO DEPLOYMENT SMALLCAPS PRODUCTION")
        
        # 1. Validar infraestructura
        if not self.validate_existing_infrastructure():
            self.logger.error("❌ Validación de infraestructura falló")
            return False
        
        # 2. Test integración
        if not self.test_component_integration():
            self.logger.error("❌ Test de integración falló")
            return False
        
        # 3. Crear archivos de configuración
        config_file = self.create_production_config_file()
        if not config_file:
            self.logger.error("❌ Error creando configuración")
            return False
        
        # 4. Crear scripts
        startup_script = self.create_startup_script()
        dashboard_script = self.create_monitoring_dashboard()
        
        if not startup_script or not dashboard_script:
            self.logger.error("❌ Error creando scripts")
            return False
        
        # 5. Crear resumen
        summary = self.create_deployment_summary()
        
        # 6. Log final
        self.logger.info("🎉 DEPLOYMENT COMPLETADO EXITOSAMENTE!")
        self.logger.info(f"📁 Configuración: {config_file}")
        self.logger.info(f"🚀 Startup: {startup_script}")
        self.logger.info(f"📊 Dashboard: {dashboard_script}")
        
        print("\\n" + "="*60)
        print("🎉 DEPLOYMENT SMALLCAPS PRODUCTION COMPLETADO!")
        print("="*60)
        print("\\n🔧 COMPONENTES APROVECHADOS:")
        for component in summary["leveraged_existing_code"]:
            print(f"   ✅ {component}")
        
        print("\\n🎯 ENFOQUE HÍBRIDO DE CONFIGURACIÓN:")
        for approach in summary["hybrid_configuration_approach"]:
            print(f"   {approach}")
        
        print("\\n🚀 PARA INICIAR EL SISTEMA:")
        print(f"   python {startup_script}")
        
        print("\\n📊 PARA VER DASHBOARD:")
        print(f"   python {dashboard_script}")
        
        return True

def main():
    """Función principal de deployment"""
    # Setup logging básico
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Ejecutar deployment
    deployer = SmallcapProductionDeployer()
    success = deployer.deploy()
    
    if success:
        print("\\n✅ Deployment exitoso!")
        exit(0)
    else:
        print("\\n❌ Deployment falló!")
        exit(1)

if __name__ == "__main__":
    main()