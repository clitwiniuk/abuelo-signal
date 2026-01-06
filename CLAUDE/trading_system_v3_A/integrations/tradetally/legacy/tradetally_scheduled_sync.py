#!/usr/bin/env python3
"""
TradeTally Scheduled Sync - End-of-Day Synchronization Service
============================================================

Servicio que sincroniza automáticamente trades con TradeTally
después del cierre del mercado regular (16:30 EST).

Características:
- Detecta cierre de mercado automáticamente
- Una sincronización diaria completa (Híbrida: PostgreSQL + API)
- Manejo de errores y reintentos
- Logs detallados de sincronización
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import threading
from pathlib import Path
import os
from dotenv import load_dotenv

from .tradetally_sync import TradeTallyIntegration

# Load environment variables from .env.local
env_path = Path(__file__).parent.parent.parent.parent / '.env.local'
if env_path.exists():
    load_dotenv(env_path)

logger = logging.getLogger(__name__)

class TradeTallyScheduledSync:
    """
    Servicio de sincronización programada para TradeTally
    
    Se ejecuta automáticamente después del cierre del mercado
    para sincronizar todos los trades cerrados del día.
    """
    
    def __init__(self, api_key: str, base_url: str, db_path: str, sync_time: str = "16:30"):
        """
        Inicializar servicio de sincronización programada
        
        Args:
            api_key: API key de TradeTally
            base_url: URL base de TradeTally API
            db_path: Ruta a la base de datos local
            sync_time: Hora de sincronización en formato HH:MM (EST)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.db_path = db_path
        self.sync_time = sync_time
        
        # Estado del servicio
        self.is_running = False
        self.last_sync_date = None
        self.sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'last_sync_result': None
        }
        
        # Thread para el scheduler
        self.scheduler_thread = None
        self.stop_event = threading.Event()
        
        # Integración TradeTally
        self.tradetally_integration = None
        
        logger.info(f"📊 TradeTally Scheduled Sync initialized - Daily sync at {sync_time} EST (22:30 Madrid)")
    
    def _create_tradetally_integration(self) -> Optional[TradeTallyIntegration]:
        """Crear instancia de TradeTally Integration"""
        try:
            if not self.api_key or len(self.api_key.strip()) < 10:
                logger.warning("⚠️ TradeTally API key not configured or invalid")
                return None
                
            integration = TradeTallyIntegration(
                api_key=self.api_key,
                base_url=self.base_url,
                db_path=self.db_path
            )
            
            # Test connection
            if integration.test_connection():
                logger.info("✅ TradeTally connection verified")
                return integration
            else:
                logger.error("❌ TradeTally connection failed")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating TradeTally integration: {e}")
            return None
    
    def start_scheduler(self):
        """Iniciar el scheduler de sincronización"""
        if self.is_running:
            logger.warning("⚠️ TradeTally scheduler already running")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        # Crear y iniciar thread del scheduler
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info(f"🕐 TradeTally scheduler started - Daily sync at {self.sync_time} EST (22:30 Madrid)")
    
    def _run_scheduler(self):
        """Loop principal del scheduler"""
        # Configurar schedule
        schedule.clear()
        schedule.every().day.at(self.sync_time).do(self._execute_sync)
        
        logger.info(f"📅 Scheduled daily TradeTally sync at {self.sync_time} EST (22:30 Madrid)")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"❌ Error in scheduler loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def _execute_sync(self):
        """Ejecutar sincronización programada (híbrida)"""
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Evitar sincronizaciones duplicadas el mismo día
        if self.last_sync_date == current_date:
            logger.info(f"📊 TradeTally sync already completed today ({current_date})")
            return

        logger.info(f"🚀 Starting scheduled TradeTally HYBRID sync for {current_date}")

        try:
            # PASO 1: Ejecutar hybrid sync (SQLite -> PostgreSQL metadata)
            logger.info("📊 Step 1/2: Syncing metadata to PostgreSQL...")
            hybrid_result = self._execute_hybrid_sync()

            # PASO 2: Crear integración si no existe
            if self.tradetally_integration is None:
                self.tradetally_integration = self._create_tradetally_integration()

            if self.tradetally_integration is None:
                logger.error("❌ Cannot create TradeTally integration")
                self.sync_stats['failed_syncs'] += 1
                return

            # PASO 2: Ejecutar sincronización a TradeTally API
            logger.info("📊 Step 2/2: Syncing to TradeTally API...")
            result = self.tradetally_integration.sync_all_trades(
                batch_size=10,
                delay=1.0
            )

            # Agregar resultados del hybrid sync
            result['hybrid_sync'] = hybrid_result

            # Actualizar estadísticas
            self.sync_stats['total_syncs'] += 1
            self.sync_stats['last_sync_result'] = result

            if result.get('success', False):
                self.sync_stats['successful_syncs'] += 1
                self.last_sync_date = current_date

                logger.info(f"""
                📊 TRADETALLY HYBRID SYNC COMPLETED SUCCESSFULLY:

                Step 1 - PostgreSQL Metadata:
                ✅ New records: {hybrid_result.get('synced', 0)}
                📋 Already synced: {hybrid_result.get('skipped', 0)}

                Step 2 - TradeTally API:
                ✅ Trades sincronizados: {result.get('synced', 0)}
                ❌ Trades fallidos: {result.get('failed', 0)}
                📈 Total procesados: {result.get('total', 0)}

                📅 Fecha: {current_date}
                """)

            else:
                self.sync_stats['failed_syncs'] += 1
                logger.error(f"❌ TradeTally sync failed: {result}")

        except Exception as e:
            logger.error(f"❌ Error during scheduled sync: {e}")
            self.sync_stats['failed_syncs'] += 1

    def _execute_hybrid_sync(self) -> Dict[str, Any]:
        """
        Ejecutar sincronización híbrida (SQLite -> PostgreSQL metadata)

        Returns:
            Dict con resultado del hybrid sync
        """
        try:
            from .tradetally_sync_hybrid import TradeTallyHybridSync

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
    
    def manual_sync(self) -> Dict[str, Any]:
        """Ejecutar sincronización manual"""
        logger.info("🔄 Manual TradeTally sync requested")
        
        try:
            if self.tradetally_integration is None:
                self.tradetally_integration = self._create_tradetally_integration()
            
            if self.tradetally_integration is None:
                return {
                    'success': False,
                    'error': 'Cannot create TradeTally integration'
                }
            
            result = self.tradetally_integration.sync_all_trades()
            
            # Update stats
            self.sync_stats['total_syncs'] += 1
            self.sync_stats['last_sync_result'] = result
            
            if result.get('success', False):
                self.sync_stats['successful_syncs'] += 1
                self.last_sync_date = datetime.now().strftime("%Y-%m-%d")
            else:
                self.sync_stats['failed_syncs'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error during manual sync: {e}")
            self.sync_stats['failed_syncs'] += 1
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Obtener estado del servicio de sincronización"""
        next_sync = "Unknown"
        if self.is_running:
            try:
                jobs = schedule.get_jobs()
                if jobs:
                    next_run = jobs[0].next_run
                    if next_run:
                        next_sync = next_run.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        return {
            'service_running': self.is_running,
            'sync_time': self.sync_time,
            'next_scheduled_sync': next_sync,
            'last_sync_date': self.last_sync_date,
            'total_syncs': self.sync_stats['total_syncs'],
            'successful_syncs': self.sync_stats['successful_syncs'],
            'failed_syncs': self.sync_stats['failed_syncs'],
            'success_rate': (
                (self.sync_stats['successful_syncs'] / self.sync_stats['total_syncs'] * 100) 
                if self.sync_stats['total_syncs'] > 0 else 0
            ),
            'api_configured': bool(self.api_key and self.api_key.startswith('tt_live_')),
            'database_path': self.db_path
        }
    
    def get_pending_trades_count(self) -> int:
        """Obtener número de trades pendientes de sincronizar"""
        try:
            if self.tradetally_integration is None:
                self.tradetally_integration = self._create_tradetally_integration()
            
            if self.tradetally_integration:
                trades = self.tradetally_integration.get_local_trades(only_new=True)
                return len(trades)
                
        except Exception as e:
            logger.error(f"❌ Error getting pending trades count: {e}")
        
        return 0
    
    def stop_scheduler(self):
        """Detener el scheduler"""
        if not self.is_running:
            return
        
        logger.info("🛑 Stopping TradeTally scheduler...")
        
        self.is_running = False
        self.stop_event.set()
        
        # Clear scheduled jobs
        schedule.clear()
        
        # Wait for thread to finish
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("✅ TradeTally scheduler stopped")
    
    def __del__(self):
        """Cleanup on destruction"""
        if self.is_running:
            self.stop_scheduler()