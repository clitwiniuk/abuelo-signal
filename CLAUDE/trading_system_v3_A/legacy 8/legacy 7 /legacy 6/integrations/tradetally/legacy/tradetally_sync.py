"""
TradeTally Integration Module
Sincroniza los trades de la base de datos local con TradeTally API
"""

import sqlite3
import requests
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import time
import os
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TradeRecord:
    """Estructura de datos para un trade"""
    id: int
    trade_id: str
    symbol: str
    strategy: str
    side: str
    quantity: int
    entry_price: float
    exit_price: Optional[float]
    entry_time: str
    exit_time: Optional[str]
    duration_minutes: Optional[int]
    pnl: Optional[float]
    commission: float
    status: str
    notes: Optional[str]
    created_at: str
    updated_at: str

class TradeTallyIntegration:
    """Integración con TradeTally API"""
    
    def __init__(self, api_key: str, base_url: str, db_path: str):
        """
        Inicializar la integración
        
        Args:
            api_key: Token de API de TradeTally (formato: tt_live_xxx)
            base_url: URL base de TradeTally (ej: https://your-domain.com/api/v2)
            db_path: Ruta a la base de datos SQLite local
        """
        # Detailed logging of initialization
        logger.info(f"🔍 TRADETALLY DEBUG - Initializing TradeTallyIntegration")
        logger.info(f"🔍 TRADETALLY DEBUG - API Key received: {api_key[:20]}{'...' if len(api_key) > 20 else ''}")
        logger.info(f"🔍 TRADETALLY DEBUG - API Key length: {len(api_key)}")
        logger.info(f"🔍 TRADETALLY DEBUG - Base URL: {base_url}")
        logger.info(f"🔍 TRADETALLY DEBUG - DB Path: {db_path}")
        
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.db_path = db_path
        self.headers = {
            'X-API-Key': api_key,
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'TradingSystemV3-Sync/1.0'
        }
        
        logger.info(f"🔍 TRADETALLY DEBUG - Final base URL: {self.base_url}")
        logger.info(f"🔍 TRADETALLY DEBUG - Authorization header created: Bearer {api_key[:20]}{'...' if len(api_key) > 20 else ''}")
        
        # Archivo para tracking de sincronización
        self.sync_state_file = Path(db_path).parent / "tradetally_sync_state.json"
        self.load_sync_state()
        
    def load_sync_state(self):
        """Cargar el estado de sincronización"""
        try:
            if self.sync_state_file.exists():
                with open(self.sync_state_file, 'r') as f:
                    self.sync_state = json.load(f)
            else:
                self.sync_state = {
                    'last_sync_timestamp': None,
                    'synced_trade_ids': [],
                    'failed_syncs': []
                }
        except Exception as e:
            logger.error(f"Error cargando estado de sync: {e}")
            self.sync_state = {
                'last_sync_timestamp': None,
                'synced_trade_ids': [],
                'failed_syncs': []
            }
    
    def save_sync_state(self):
        """Guardar el estado de sincronización"""
        try:
            with open(self.sync_state_file, 'w') as f:
                json.dump(self.sync_state, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando estado de sync: {e}")
    
    def test_connection(self) -> bool:
        """Probar la conexión con TradeTally API"""
        try:
            # Detailed logging of the request being made
            url = f"{self.base_url}/trades?limit=1"
            logger.info(f"🔍 TRADETALLY DEBUG - Testing connection to: {url}")
            logger.info(f"🔍 TRADETALLY DEBUG - API Key format: {self.api_key[:20]}{'...' if len(self.api_key) > 20 else ''}")
            logger.info(f"🔍 TRADETALLY DEBUG - API Key length: {len(self.api_key)}")
            logger.info(f"🔍 TRADETALLY DEBUG - API Key starts with: {self.api_key[:10] if len(self.api_key) >= 10 else self.api_key}")
            logger.info(f"🔍 TRADETALLY DEBUG - Headers being sent:")
            for key, value in self.headers.items():
                if key == 'Authorization':
                    logger.info(f"  {key}: Bearer {value.split(' ')[1][:20]}{'...' if len(value.split(' ')[1]) > 20 else ''}")
                else:
                    logger.info(f"  {key}: {value}")
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=30
            )
            
            # Detailed logging of the response
            logger.info(f"🔍 TRADETALLY DEBUG - Response status code: {response.status_code}")
            logger.info(f"🔍 TRADETALLY DEBUG - Response headers:")
            for key, value in response.headers.items():
                logger.info(f"  {key}: {value}")
            
            logger.info(f"🔍 TRADETALLY DEBUG - Response body: {response.text}")
            
            if response.status_code == 200:
                logger.info("✅ Conexión exitosa con TradeTally API")
                try:
                    response_json = response.json()
                    logger.info(f"🔍 TRADETALLY DEBUG - Response JSON: {json.dumps(response_json, indent=2)}")
                except:
                    logger.info("🔍 TRADETALLY DEBUG - Response is not valid JSON")
                return True
            elif response.status_code == 401:
                logger.error("❌ API Key inválida o expirada")
                logger.error(f"🔍 TRADETALLY DEBUG - Full 401 response: {response.text}")
                return False
            else:
                logger.error(f"❌ Error de conexión: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de red: {e}")
            logger.error(f"🔍 TRADETALLY DEBUG - Full exception: {str(e)}")
            import traceback
            logger.error(f"🔍 TRADETALLY DEBUG - Traceback: {traceback.format_exc()}")
            return False
    
    def get_local_trades(self, only_new: bool = True) -> List[TradeRecord]:
        """
        Obtener trades de la base de datos local con información del ML
        
        Args:
            only_new: Si True, solo obtiene trades no sincronizados
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Para acceso por nombre de columna
            cursor = conn.cursor()
            
            # Enhanced query using real execution prices for TradeTally
            base_query = """
                SELECT t.*, 
                       -- Use actual execution prices if available, fallback to planned
                       COALESCE(t.actual_entry_price, t.entry_price) as final_entry_price,
                       COALESCE(t.actual_exit_price, t.exit_price) as final_exit_price,
                       COALESCE(t.actual_entry_time, t.entry_time) as final_entry_time,
                       COALESCE(t.actual_exit_time, t.exit_time) as final_exit_time,
                       COALESCE(t.actual_pnl, t.pnl) as final_pnl,
                       -- Slippage data for enriched notes
                       t.entry_slippage,
                       t.exit_slippage,
                       t.entry_slippage_pct,
                       t.exit_slippage_pct,
                       t.total_slippage_impact,
                       -- ML data
                       atr.trade_category,
                       atr.context_type,
                       atr.market_context,
                       atr.why_in_play,
                       atr.daily_volume_context,
                       atr.intraday_volume_context,
                       atr.daily_chart_analysis,
                       atr.intraday_chart_analysis,
                       atr.how_you_traded,
                       atr.followed_system,
                       atr.sizing_appropriate,
                       atr.execution_quality,
                       atr.how_should_have_traded,
                       atr.key_takeaways,
                       atr.changes_to_make,
                       atr.strategy_used as ml_strategy
                FROM trades t
                LEFT JOIN advanced_trading_results atr ON t.trade_id = atr.trade_id
            """
            
            if only_new and self.sync_state['synced_trade_ids']:
                # Solo trades no sincronizados
                placeholders = ','.join(['?' for _ in self.sync_state['synced_trade_ids']])
                query = f"{base_query} WHERE t.trade_id NOT IN ({placeholders}) AND t.status = 'CLOSED' ORDER BY t.entry_time DESC"
                cursor.execute(query, self.sync_state['synced_trade_ids'])
            else:
                # Todos los trades cerrados
                query = f"{base_query} WHERE t.status = 'CLOSED' ORDER BY t.entry_time DESC"
                cursor.execute(query)
            
            rows = cursor.fetchall()
            trades = []
            
            for row in rows:
                # Crear trade con información adicional del ML
                trade = TradeRecord(
                    id=row['id'],
                    trade_id=row['trade_id'],
                    symbol=row['symbol'],
                    strategy=row['strategy'],
                    side=row['side'],
                    quantity=row['quantity'],
                    entry_price=row['entry_price'],
                    exit_price=row['exit_price'],
                    entry_time=row['entry_time'],
                    exit_time=row['exit_time'],
                    duration_minutes=row['duration_minutes'],
                    pnl=row['pnl'],
                    commission=row['commission'] or 0,
                    status=row['status'],
                    notes=row['notes'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                
                # Agregar información del ML como atributos adicionales
                trade.ml_data = {
                    'trade_category': row['trade_category'],
                    'context_type': row['context_type'],
                    'market_context': row['market_context'],
                    'why_in_play': row['why_in_play'],
                    'daily_volume_context': row['daily_volume_context'],
                    'intraday_volume_context': row['intraday_volume_context'],
                    'daily_chart_analysis': row['daily_chart_analysis'],
                    'intraday_chart_analysis': row['intraday_chart_analysis'],
                    'how_you_traded': row['how_you_traded'],
                    'followed_system': row['followed_system'],
                    'sizing_appropriate': row['sizing_appropriate'],
                    'execution_quality': row['execution_quality'],
                    'how_should_have_traded': row['how_should_have_traded'],
                    'key_takeaways': row['key_takeaways'],
                    'changes_to_make': row['changes_to_make'],
                    'ml_strategy': row['ml_strategy']
                }
                
                trades.append(trade)
            
            conn.close()
            logger.info(f"📊 Encontrados {len(trades)} trades para sincronizar")
            return trades
            
        except Exception as e:
            logger.error(f"Error obteniendo trades locales: {e}")
            return []
    
    def convert_side(self, side: str) -> str:
        """Convertir side de formato local a TradeTally"""
        side_mapping = {
            'BUY': 'long',
            'SELL': 'short'
        }
        return side_mapping.get(side.upper(), 'long')
    
    def format_datetime(self, dt_str: str) -> str:
        """Convertir timestamp a formato ISO con timezone"""
        try:
            # Parsear diferentes formatos de fecha
            if isinstance(dt_str, str):
                # Intentar varios formatos
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S.%fZ'
                ]
                
                dt = None
                for fmt in formats:
                    try:
                        dt = datetime.strptime(dt_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if dt is None:
                    logger.warning(f"No se pudo parsear fecha: {dt_str}")
                    return dt_str
                
                # Asegurar timezone UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                return dt.isoformat()
            
            return dt_str
            
        except Exception as e:
            logger.error(f"Error formateando fecha {dt_str}: {e}")
            return dt_str
    
    def create_enhanced_tags(self, trade: TradeRecord) -> List[str]:
        """Crear tags automáticos basados en datos de la BBDD"""
        tags = []
        
        # Tag de estrategia de la BBDD
        if trade.strategy:
            tags.append(trade.strategy.lower().replace('_', '-'))
        
        # Tags del ML si existen en la BBDD
        if hasattr(trade, 'ml_data') and trade.ml_data:
            ml_data = trade.ml_data
            
            if ml_data.get('trade_category'):
                tags.append(ml_data['trade_category'].lower().replace(' ', '-'))
            
            if ml_data.get('context_type'):
                tags.append(ml_data['context_type'].lower().replace(' ', '-'))
            
            if ml_data.get('ml_strategy'):
                tags.append(f"ml-{ml_data['ml_strategy'].lower().replace('_', '-')}")
        
        # Tags de rendimiento basado en PnL real
        if trade.pnl:
            if trade.pnl > 0:
                tags.append('winner')
            else:
                tags.append('loser')
        
        # Tag de duración basado en datos reales
        if trade.duration_minutes:
            if trade.duration_minutes < 30:
                tags.append('scalp')
            elif trade.duration_minutes < 240:
                tags.append('intraday')
            else:
                tags.append('swing')
        
        return list(set(tags))  # Eliminar duplicados
    
    def create_tradetally_payload(self, trade: TradeRecord) -> Dict:
        """Crear payload enriquecido para TradeTally API usando precios reales de ejecución"""
        # Use real execution prices if available, fallback to planned prices
        entry_price = getattr(trade, 'final_entry_price', None) or trade.entry_price
        exit_price = getattr(trade, 'final_exit_price', None) or trade.exit_price
        entry_time = getattr(trade, 'final_entry_time', None) or trade.entry_time
        exit_time = getattr(trade, 'final_exit_time', None) or trade.exit_time
        
        payload = {
            'symbol': trade.symbol,
            'side': self.convert_side(trade.side),
            'entryTime': self.format_datetime(entry_time),
            'entryPrice': entry_price,
            'quantity': trade.quantity,
            'commission': trade.commission,
            'strategy': trade.strategy or 'Unknown',
            'broker': 'IBKR',
            'tags': self.create_enhanced_tags(trade)
        }
        
        # Campos opcionales solo si existen
        if exit_time:
            payload['exitTime'] = self.format_datetime(exit_time)
        
        if exit_price:
            payload['exitPrice'] = exit_price
        
        # Setup basado en ML data de la BBDD
        if hasattr(trade, 'ml_data') and trade.ml_data and trade.ml_data.get('trade_category'):
            payload['setup'] = trade.ml_data['trade_category']
        
        # Crear notas enriquecidas con información de la BBDD
        notes_sections = []
        
        # Notas originales
        if trade.notes:
            notes_sections.append(f"Original Notes: {trade.notes}")
        
        # Información básica y de slippage
        basic_info = [f"Trade ID: {trade.trade_id}"]
        if trade.duration_minutes:
            hours = trade.duration_minutes // 60
            mins = trade.duration_minutes % 60
            duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            basic_info.append(f"Duration: {duration_str}")
        
        # Add slippage information if available
        slippage_info = []
        if hasattr(trade, 'entry_slippage') and trade.entry_slippage is not None:
            slippage_info.append(f"Entry Slippage: ${trade.entry_slippage:.4f}")
        if hasattr(trade, 'exit_slippage') and trade.exit_slippage is not None:
            slippage_info.append(f"Exit Slippage: ${trade.exit_slippage:.4f}")
        if hasattr(trade, 'total_slippage_impact') and trade.total_slippage_impact is not None:
            slippage_info.append(f"Total Slippage Impact: ${trade.total_slippage_impact:.2f}")
        
        if slippage_info:
            basic_info.extend(slippage_info)
        
        notes_sections.append(" | ".join(basic_info))
        
        # Información del ML si existe en la BBDD
        if hasattr(trade, 'ml_data') and trade.ml_data:
            ml_data = trade.ml_data
            ml_notes = []
            
            if ml_data.get('market_context'):
                ml_notes.append(f"Market Context: {ml_data['market_context']}")
            
            if ml_data.get('why_in_play'):
                ml_notes.append(f"Why In Play: {ml_data['why_in_play']}")
            
            if ml_data.get('execution_quality'):
                ml_notes.append(f"Execution: {ml_data['execution_quality']}")
            
            if ml_data.get('followed_system') is not None:
                system_follow = "Yes" if ml_data['followed_system'] else "No"
                ml_notes.append(f"Followed System: {system_follow}")
            
            if ml_data.get('key_takeaways'):
                ml_notes.append(f"Key Takeaways: {ml_data['key_takeaways']}")
            
            if ml_notes:
                notes_sections.append("ML Analysis: " + " | ".join(ml_notes))
        
        # Combinar todas las secciones de notas
        if notes_sections:
            payload['notes'] = "\n\n".join(notes_sections)
        
        return payload
    
    def sync_trade_to_tradetally(self, trade: TradeRecord) -> Tuple[bool, str]:
        """
        Sincronizar un trade individual con TradeTally
        
        Returns:
            Tuple[bool, str]: (success, message/error)
        """
        try:
            payload = self.create_tradetally_payload(trade)
            
            logger.info(f"🔄 Sincronizando trade {trade.symbol} - {trade.trade_id}")
            
            response = requests.post(
                f"{self.base_url}/trades",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Trade {trade.trade_id} sincronizado exitosamente")
                return True, "Success"
            
            elif response.status_code == 429:
                logger.warning("⚠️ Rate limit alcanzado, pausando...")
                time.sleep(60)  # Pausa de 1 minuto
                return False, "Rate limited"
            
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                logger.error(f"❌ Error sincronizando {trade.trade_id}: {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Excepción: {str(e)}"
            logger.error(f"❌ Error sincronizando {trade.trade_id}: {error_msg}")
            return False, error_msg
    
    def sync_all_trades(self, batch_size: int = 10, delay: float = 1.0) -> Dict:
        """
        Sincronizar todos los trades pendientes
        
        Args:
            batch_size: Número de trades por lote
            delay: Pausa entre requests (segundos)
        
        Returns:
            Dict con estadísticas de sincronización
        """
        logger.info("🚀 Iniciando sincronización con TradeTally...")
        
        # Verificar conexión
        if not self.test_connection():
            return {
                'success': False,
                'error': 'No se pudo conectar con TradeTally API',
                'synced': 0,
                'failed': 0
            }
        
        # Obtener trades para sincronizar
        trades = self.get_local_trades(only_new=True)
        
        if not trades:
            logger.info("✅ No hay trades nuevos para sincronizar")
            return {
                'success': True,
                'message': 'No hay trades nuevos',
                'synced': 0,
                'failed': 0
            }
        
        stats = {
            'total': len(trades),
            'synced': 0,
            'failed': 0,
            'errors': []
        }
        
        # Procesar en lotes
        for i in range(0, len(trades), batch_size):
            batch = trades[i:i + batch_size]
            logger.info(f"📦 Procesando lote {i//batch_size + 1} ({len(batch)} trades)")
            
            for trade in batch:
                success, message = self.sync_trade_to_tradetally(trade)
                
                if success:
                    stats['synced'] += 1
                    # Agregar a la lista de sincronizados
                    if trade.trade_id not in self.sync_state['synced_trade_ids']:
                        self.sync_state['synced_trade_ids'].append(trade.trade_id)
                else:
                    stats['failed'] += 1
                    stats['errors'].append(f"{trade.trade_id}: {message}")
                    # Agregar a fallos
                    self.sync_state['failed_syncs'].append({
                        'trade_id': trade.trade_id,
                        'error': message,
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Pausa entre requests
                if delay > 0:
                    time.sleep(delay)
            
            # Pausa entre lotes
            if i + batch_size < len(trades):
                logger.info(f"⏸️ Pausa entre lotes...")
                time.sleep(2)
        
        # Actualizar timestamp de última sincronización
        self.sync_state['last_sync_timestamp'] = datetime.now().isoformat()
        self.save_sync_state()
        
        # Reporte final
        logger.info(f"""
        📊 REPORTE DE SINCRONIZACIÓN COMPLETADO:
        ✅ Trades sincronizados: {stats['synced']}
        ❌ Trades fallidos: {stats['failed']}
        📈 Total procesados: {stats['total']}
        """)
        
        return {
            'success': True,
            'synced': stats['synced'],
            'failed': stats['failed'],
            'total': stats['total'],
            'errors': stats['errors']
        }
    
    def get_sync_status(self) -> Dict:
        """Obtener estado actual de sincronización"""
        return {
            'last_sync': self.sync_state.get('last_sync_timestamp'),
            'total_synced': len(self.sync_state.get('synced_trade_ids', [])),
            'failed_syncs': len(self.sync_state.get('failed_syncs', [])),
            'sync_state_file': str(self.sync_state_file)
        }
    
    def retry_failed_syncs(self) -> Dict:
        """Reintentar sincronización de trades fallidos"""
        failed_trade_ids = [f['trade_id'] for f in self.sync_state.get('failed_syncs', [])]
        
        if not failed_trade_ids:
            return {'success': True, 'message': 'No hay trades fallidos para reintentar'}
        
        logger.info(f"🔄 Reintentando {len(failed_trade_ids)} trades fallidos...")
        
        # Limpiar la lista de fallos
        self.sync_state['failed_syncs'] = []
        
        # Obtener trades específicos
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in failed_trade_ids])
        query = f"SELECT * FROM trades WHERE trade_id IN ({placeholders})"
        cursor.execute(query, failed_trade_ids)
        
        rows = cursor.fetchall()
        trades = [TradeRecord(**dict(row)) for row in rows]
        conn.close()
        
        # Procesar reintento
        stats = {'synced': 0, 'failed': 0}
        
        for trade in trades:
            success, message = self.sync_trade_to_tradetally(trade)
            
            if success:
                stats['synced'] += 1
                if trade.trade_id not in self.sync_state['synced_trade_ids']:
                    self.sync_state['synced_trade_ids'].append(trade.trade_id)
            else:
                stats['failed'] += 1
                self.sync_state['failed_syncs'].append({
                    'trade_id': trade.trade_id,
                    'error': message,
                    'timestamp': datetime.now().isoformat()
                })
            
            time.sleep(1)  # Pausa entre requests
        
        self.save_sync_state()
        
        return {
            'success': True,
            'synced': stats['synced'],
            'failed': stats['failed'],
            'total': len(trades)
        }


def main():
    """Función principal para testing"""
    import sys
    
    # Configuración por defecto (personalizar según tu setup)
    API_KEY = os.getenv('TRADETALLY_API_KEY', 'tt_live_your_api_key_here')
    BASE_URL = os.getenv('TRADETALLY_BASE_URL', 'https://your-domain.com/api/v2')
    DB_PATH = '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db'
    
    if API_KEY == 'tt_live_your_api_key_here':
        print("❌ Por favor configura tu API_KEY de TradeTally")
        sys.exit(1)
    
    # Crear instancia de integración
    sync = TradeTallyIntegration(API_KEY, BASE_URL, DB_PATH)
    
    # Probar conexión
    if not sync.test_connection():
        print("❌ No se pudo conectar con TradeTally")
        sys.exit(1)
    
    # Mostrar estado
    status = sync.get_sync_status()
    print(f"📊 Estado actual: {json.dumps(status, indent=2)}")
    
    # Sincronizar
    result = sync.sync_all_trades()
    print(f"🏁 Resultado: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()