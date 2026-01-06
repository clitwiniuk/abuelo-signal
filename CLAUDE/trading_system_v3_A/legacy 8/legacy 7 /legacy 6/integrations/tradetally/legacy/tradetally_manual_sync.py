#!/usr/bin/env python3
"""
TradeTally Manual Sync - Independent Manual Synchronization Service
===================================================================

Servicio independiente para sincronización manual de TradeTally
que no interfiere con el servicio automático programado.

Características:
- Sincronización manual bajo demanda
- No depende del scheduler automático
- Manejo de errores específico para comandos manuales
- Logs independientes del servicio automático
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import os
from dotenv import load_dotenv

from .tradetally_sync import TradeTallyIntegration

# Load environment variables from .env.local
env_path = Path(__file__).parent.parent.parent.parent / '.env.local'
if env_path.exists():
    load_dotenv(env_path)
    logger = logging.getLogger(__name__)
    logger.info(f"Loaded environment variables from {env_path}")
else:
    logger = logging.getLogger(__name__)
    logger.warning(f".env.local not found at {env_path}")

class TradeTallyManualSync:
    """
    Servicio de sincronización manual independiente

    Este servicio es completamente independiente del scheduler automático
    y puede ejecutarse en cualquier momento sin interferir con
    las sincronizaciones programadas.
    """

    def __init__(self, api_key: str, base_url: str, db_path: str):
        """
        Inicializar servicio de sincronización manual

        Args:
            api_key: API key de TradeTally
            base_url: URL base de TradeTally API
            db_path: Ruta a la base de datos local
        """
        self.api_key = api_key
        self.base_url = base_url
        self.db_path = db_path

        # Estado del servicio manual
        self.manual_sync_stats = {
            'total_manual_syncs': 0,
            'successful_manual_syncs': 0,
            'failed_manual_syncs': 0,
            'last_manual_sync': None
        }

        logger.info("🔧 TradeTally Manual Sync initialized")

    def _create_integration(self) -> Optional[TradeTallyIntegration]:
        """Crear instancia de integración para uso manual"""
        try:
            if not self.api_key or len(self.api_key.strip()) < 10:
                logger.warning("⚠️ TradeTally API key not configured")
                return None

            integration = TradeTallyIntegration(
                api_key=self.api_key,
                base_url=self.base_url,
                db_path=self.db_path
            )

            # Test connection
            if integration.test_connection():
                logger.info("✅ TradeTally manual connection verified")
                return integration
            else:
                logger.error("❌ TradeTally manual connection failed")
                return None

        except Exception as e:
            logger.error(f"❌ Error creating manual TradeTally integration: {e}")
            return None

    def execute_manual_sync(self, only_today: bool = False) -> Dict[str, Any]:
        """
        Ejecutar sincronización manual (híbrida)

        Ejecuta dos tipos de sincronización:
        1. Hybrid sync: SQLite -> PostgreSQL (metadata)
        2. TradeTally API sync: SQLite -> TradeTally API (completo)

        Args:
            only_today: Si True, solo sincroniza trades de hoy

        Returns:
            Dict con resultado de la sincronización
        """
        logger.info(f"🔄 Manual TradeTally sync requested (only_today={only_today})")

        try:
            # PASO 1: Ejecutar hybrid sync (SQLite -> PostgreSQL metadata)
            logger.info("📊 Step 1/2: Syncing metadata to PostgreSQL...")
            hybrid_result = self._execute_hybrid_sync()

            # PASO 2: Crear integración para TradeTally API
            integration = self._create_integration()

            if integration is None:
                error_msg = "Cannot create TradeTally integration"
                logger.error(f"❌ {error_msg}")

                self.manual_sync_stats['total_manual_syncs'] += 1
                self.manual_sync_stats['failed_manual_syncs'] += 1

                return {
                    'success': False,
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat(),
                    'hybrid_sync': hybrid_result
                }

            # PASO 2: Ejecutar sincronización a TradeTally API
            logger.info("📊 Step 2/2: Syncing to TradeTally API...")
            result = integration.sync_all_trades(only_today=only_today)

            # Actualizar estadísticas manuales
            self.manual_sync_stats['total_manual_syncs'] += 1
            self.manual_sync_stats['last_manual_sync'] = datetime.now().isoformat()

            if result.get('success', False):
                self.manual_sync_stats['successful_manual_syncs'] += 1
                logger.info(f"✅ Manual sync completed: {result.get('synced', 0)} trades synced to API")
            else:
                self.manual_sync_stats['failed_manual_syncs'] += 1
                logger.error(f"❌ Manual sync failed: {result}")

            # Agregar timestamp y datos de hybrid sync al resultado
            result['timestamp'] = datetime.now().isoformat()
            result['manual_sync'] = True
            result['hybrid_sync'] = hybrid_result

            return result

        except Exception as e:
            logger.error(f"❌ Error during manual sync: {e}")

            self.manual_sync_stats['total_manual_syncs'] += 1
            self.manual_sync_stats['failed_manual_syncs'] += 1

            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'manual_sync': True
            }

    def _execute_hybrid_sync(self) -> Dict[str, Any]:
        """
        Ejecutar sincronización híbrida (SQLite -> PostgreSQL metadata)

        Returns:
            Dict con resultado del hybrid sync
        """
        try:
            from .tradetally_sync_hybrid import TradeTallyHybridSync
            import os

            # Configuración de PostgreSQL desde variables de entorno
            pg_config = {
                'host': os.getenv('PG_HOST', 'localhost'),
                'port': int(os.getenv('PG_PORT', '5432')),
                'database': os.getenv('PG_DATABASE', 'carlos'),
                'user': os.getenv('PG_USER', 'carlos'),
                'password': os.getenv('PG_PASSWORD', '')
            }

            user_id = os.getenv('TRADETALLY_USER_ID', '7ab22590-ebff-4cc0-b2c3-43170dda53d2')

            # Crear instancia de hybrid sync
            hybrid_sync = TradeTallyHybridSync(
                sqlite_db_path=self.db_path,
                pg_config=pg_config,
                user_id=user_id
            )

            # Ejecutar sincronización
            stats = hybrid_sync.sync_all_trades(dry_run=False)

            logger.info(f"✅ Hybrid sync completed: {stats['synced']} metadata records synced to PostgreSQL")

            return {
                'success': True,
                'synced': stats['synced'],
                'skipped': stats['skipped'],
                'errors': stats['errors'],
                'total': stats['total']
            }

        except Exception as e:
            logger.error(f"❌ Error in hybrid sync: {e}")
            return {
                'success': False,
                'error': str(e),
                'synced': 0
            }

    def get_manual_sync_status(self) -> Dict[str, Any]:
        """Obtener estado del servicio de sincronización manual"""
        return {
            'manual_sync_stats': self.manual_sync_stats,
            'api_configured': bool(self.api_key and self.api_key.startswith('tt_live_')),
            'base_url': self.base_url,
            'database_path': self.db_path
        }