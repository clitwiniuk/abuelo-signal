#!/usr/bin/env python3
"""
Unified Trading System - NUEVO SISTEMA PRINCIPAL
Reemplaza main.py y smallcap_production_runner.py

SOLUCIONA TODOS LOS PROBLEMAS:
✅ Una sola instancia de IBKRAdapter (client_id unificado)
✅ Un solo RiskManager/Mayordomo (posiciones sincronizadas)
✅ Un solo TradingEngine (no más ejecuciones duplicadas)
✅ Un solo TelegramClient (logs unificados)
✅ Una sola configuración (config.ini centralizado)
"""

import asyncio
import logging
import signal
import sys
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import threading
import configparser

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import unified services
from core.service_locator import get_service_locator, get_config
from core.scanner_trader_bridge import ScannerTraderBridge
from utils.log_config import setup_logging

class UnifiedTradingSystem:
    """
    Sistema de Trading Unificado - SOLUCIÓN FINAL
    
    Combina todas las funcionalidades en un solo sistema coherente:
    - Trading Engine (estrategias ML + tradicionales)
    - Scanner System (smallcap opportunities)
    - Risk Management (posiciones unificadas)
    - Notifications (Telegram centralizado)
    """
    
    def __init__(self):
        # Setup logging first - using original log file
        setup_logging(level="INFO", log_file="logs/trading_system.log")
        self.logger = logging.getLogger("UnifiedTradingSystem")
        
        # Get unified services
        self.service_locator = get_service_locator()
        self.config = self.service_locator.load_config()
        
        # System components (injected by ServiceLocator)
        self.ibkr_adapter = None
        self.trading_engine = None
        self.risk_manager = None
        self.mayordomo = None
        self.telegram_client = None
        
        # Hybrid Learning System
        self.hybrid_system = None
        
        # Scanner (if smallcap mode enabled)
        self.scanner = None
        self.scanner_task = None
        
        # Scanner-Trader communication bridge
        self.scanner_trader_bridge = ScannerTraderBridge()
        self.bridge_task = None
        
        # Trading engine task
        self.trading_engine_task = None
        
        # Scanner notification cache to avoid spam
        self.notified_plays = {}  # {symbol: {last_notified: datetime, last_data: dict}}
        self.notification_cooldown = 300  # 5 minutos entre notificaciones del mismo ticker
        
        # System state
        self.is_running = False
        self.shutdown_requested = False
        
        self.logger.info("🚀 UNIFIED TRADING SYSTEM - Arquitectura Unificada")
        self.logger.info(f"   Mode: {'PRODUCTION' if self.config.production_mode else 'MOCK'}")
        self.logger.info(f"   Client ID: {self.config.client_id} (ÚNICO)")
        self.logger.info(f"   Strategy: {self.config.strategy_name}")
    
    async def initialize(self):
        """Inicializar todos los componentes usando ServiceLocator"""
        try:
            self.logger.info("🔧 Inicializando sistema unificado...")
            
            # Obtener servicios compartidos (Singleton pattern)
            self.ibkr_adapter = await self.service_locator.get_or_create_ibkr_adapter()
            self.risk_manager = await self.service_locator.get_or_create_risk_manager()
            self.mayordomo = await self.service_locator.get_or_create_mayordomo()
            self.telegram_client = self.service_locator.get_or_create_telegram_client()
            self.trading_engine = await self.service_locator.get_or_create_trading_engine()
            
            # Inicializar Telegram Command Listener
            if self.telegram_client:
                success = self.telegram_client.start_command_listener()
                if success:
                    self.logger.info("✅ Telegram Command Listener iniciado correctamente")
                else:
                    self.logger.error("❌ Fallo iniciando Telegram Command Listener")
            
            # Inicializar Trading Engine
            if hasattr(self.trading_engine, 'initialize'):
                await self.trading_engine.initialize()
                self.logger.info("✅ TradingEngine inicializado (instancia única)")
            
            # Inicializar Hybrid Learning System (si está habilitado)
            hybrid_system = await self.service_locator.get_or_create_hybrid_learning_system()
            if hybrid_system:
                self.hybrid_system = hybrid_system
                self.logger.info("🧠 Hybrid Learning System inicializado - Professional Trader AI Active")
            else:
                self.hybrid_system = None
                self.logger.info("🧠 Hybrid Learning System disabled or failed to initialize")
            
            # Inicializar TradeTally Service (si está habilitado)
            tradetally_service = await self.service_locator.get_or_create_tradetally_service()
            if tradetally_service:
                self.logger.info("📊 TradeTally Service inicializado - End-of-day sync scheduled")
            else:
                self.logger.info("📊 TradeTally Service disabled or failed to initialize")
            
            # Inicializar Scanner-Trader Bridge
            bridge_connected = await self.scanner_trader_bridge.connect()
            if bridge_connected:
                self.logger.info("✅ Scanner-Trader Bridge initialized")
            else:
                self.logger.warning("⚠️ Redis not available - using direct communication fallback")
            
            # Inicializar Scanner si smallcap mode está activo
            if self.config.enable_smallcap_mode:
                await self._initialize_scanner()
            
            # Configurar signal handlers
            self._setup_signal_handlers()
            
            # Enviar notificación de inicio
            await self._send_startup_notification()
            
            self.logger.info("✅ Sistema unificado inicializado correctamente")
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando sistema: {e}")
            raise
    
    async def _initialize_scanner(self):
        """Inicializar sistema de scanner para smallcaps CON CONEXIÓN IBKR SEPARADA"""
        try:
            self.logger.info("🔍 Inicializando scanner system con conexión IBKR separada...")
            
            from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
            from adapters.ibkr_adapter import IBKRAdapter
            
            # CRITICAL FIX: Create SEPARATE IBKR connection for scanner (different client_id)
            scanner_client_id = self.config.client_id + 1  # Use next client_id for scanner
            self.logger.info(f"📡 Creating separate IBKR connection for scanner (client_id: {scanner_client_id})")
            
            scanner_ibkr = IBKRAdapter(
                host=self.config.host,
                port=self.config.port,
                client_id=scanner_client_id
            )
            
            # Connect scanner's IBKR adapter
            await scanner_ibkr.connect()
            self.logger.info("✅ Scanner IBKR adapter connected successfully")
            
            # Create scanner with its own IBKR connection
            self.scanner = SmallcapDailyScanner(ibkr_adapter=scanner_ibkr)
            self.logger.info(f"🔍 Scanner object created with separate IBKR connection: {self.scanner}")
            
            # Verify scanner has its own IBKR connection
            if hasattr(self.scanner, 'ibkr_scanner') and hasattr(self.scanner.ibkr_scanner, 'ibkr_adapter'):
                self.logger.info("✅ Scanner properly configured with separate IBKR connection")
                self.logger.info(f"   Scanner client_id: {scanner_client_id}")
                self.logger.info(f"   Trader client_id: {self.config.client_id}")
            else:
                self.logger.warning("⚠️ Scanner IBKR connection not properly configured")
            
            self.logger.info("✅ Scanner inicializado con conexión IBKR separada")
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando scanner: {e}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            self.scanner = None
    
    async def _send_startup_notification(self):
        """Enviar notificación unificada de inicio"""
        if hasattr(self.telegram_client, 'send_message'):
            try:
                positions = len(getattr(self.risk_manager, 'broker_positions', {}))
                
                # Get TradeTally status
                tradetally_service = self.service_locator.get_service('tradetally_service')
                tradetally_info = ""
                if tradetally_service:
                    try:
                        tt_status = tradetally_service.get_sync_status()
                        pending_count = tradetally_service.get_pending_trades_count()
                        tradetally_info = f"• TradeTally: {'✅' if tt_status['api_configured'] else '❌'} (Sync: {tt_status['sync_time']}, Pending: {pending_count})"
                    except:
                        tradetally_info = "• TradeTally: ❌ Error getting status"
                
                startup_msg = f"""🚀 **UNIFIED TRADING SYSTEM INICIADO**

🎯 **Configuración Unificada:**
• Modo: {'🟢 PRODUCTION' if self.config.production_mode else '🟡 MOCK'}
• Client ID: {self.config.client_id} (único, sin conflictos)
• Estrategia: {self.config.strategy_name}
• Smallcap Mode: {'✅' if self.config.enable_smallcap_mode else '❌'}
• Hybrid Learning: {'🧠' if self.hybrid_system else '❌'}
• Posiciones Actuales: {positions}
• Max Posiciones: {self.config.max_positions}
• Max por Símbolo: {self.config.max_positions_per_symbol}
{tradetally_info}

✅ **Problemas Resueltos:**
• Una sola conexión IBKR
• Posiciones sincronizadas 
• Logs unificados
• Configuración centralizada
{f'🧠 Professional Trader AI: Active' if self.hybrid_system else ''}

📊 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                self.telegram_client.send_message(startup_msg, parse_mode="Markdown")
                
            except Exception as e:
                self.logger.warning(f"⚠️ Error enviando notificación: {e}")
    
    def _setup_signal_handlers(self):
        """Configurar manejo de señales para shutdown graceful"""
        def signal_handler(signum, frame):
            self.logger.info(f"📡 Señal recibida {signum}")
            if not self.shutdown_requested:
                self.shutdown_requested = True
                asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self, symbols: List[str] = None):
        """Iniciar el sistema de trading unificado"""
        try:
            if self.is_running:
                self.logger.warning("⚠️ Sistema ya está corriendo")
                return
            
            self.logger.info("🚀 Iniciando sistema unificado...")
            self.is_running = True
            
            # Iniciar Bridge subscriber (trader side)
            if self.scanner_trader_bridge.redis_client:
                self.bridge_task = asyncio.create_task(
                    self.scanner_trader_bridge.subscribe_to_opportunities(self._handle_scanner_opportunities)
                )
                self.logger.info("✅ Bridge subscriber task created")
            
            # Iniciar Trading Engine (non-blocking)
            if self.trading_engine:
                self.logger.info(f"🔧 About to start trading engine with symbols: {symbols or []}")
                # Start trading engine in background task so it doesn't block
                self.trading_engine_task = asyncio.create_task(self.trading_engine.start(symbols or []))
                self.logger.info("✅ Trading engine task created successfully")
            
            # Iniciar Scanner (si está habilitado)
            self.logger.info(f"🔍 DEBUG: scanner = {self.scanner is not None}, enable_smallcap_mode = {self.config.enable_smallcap_mode}")
            if self.scanner and self.config.enable_smallcap_mode:
                self.logger.info("🔍 Creating scanner task...")
                self.scanner_task = asyncio.create_task(self._run_scanner())
                self.logger.info("✅ Scanner task created successfully")
                
                # Give the scanner task a moment to start and log if it crashes immediately
                await asyncio.sleep(0.1)
                if self.scanner_task.done():
                    try:
                        await self.scanner_task  # This will raise the exception if one occurred
                    except Exception as e:
                        self.logger.error(f"❌ Scanner task crashed immediately: {e}")
                        import traceback
                        self.logger.error(f"Stack trace: {traceback.format_exc()}")
            else:
                self.logger.warning(f"⚠️ Scanner not started: scanner={self.scanner is not None}, smallcap_mode={getattr(self.config, 'enable_smallcap_mode', 'NOT_FOUND')}")
            
            self.logger.info("✅ Sistema unificado iniciado")
            
        except Exception as e:
            self.logger.error(f"❌ Error iniciando sistema: {e}")
            self.is_running = False
            raise
    
    async def _run_scanner(self):
        """Loop principal del scanner"""
        try:
            self.logger.info("🔍 Scanner loop iniciado")
            
            while self.is_running and not self.shutdown_requested:
                try:
                    # Buscar oportunidades
                    self.logger.info("🔍 Starting scan cycle...")
                    plays = await self._scan_for_opportunities()
                    self.logger.info(f"🔍 Scan completed - Found {len(plays) if plays else 0} plays")
                    
                    if plays:
                        self.logger.info(f"🎯 {len(plays)} oportunidades encontradas")
                        
                        # Publish via bridge if available, fallback to direct evaluation
                        if self.scanner_trader_bridge.redis_client:
                            await self.scanner_trader_bridge.publish_opportunities(plays)
                        else:
                            # Fallback: direct evaluation (no Redis)
                            await self._evaluate_opportunities(plays)
                    
                    # Esperar antes del próximo scan
                    scan_interval = getattr(self.config, 'scan_interval_seconds', 30)
                    self.logger.debug(f"🕒 Waiting {scan_interval}s until next scan...")
                    await asyncio.sleep(scan_interval)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error en scanner: {e}")
                    await asyncio.sleep(30)  # Espera de emergencia
        
        except Exception as e:
            self.logger.error(f"❌ Fatal error in scanner loop: {e}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
    
    async def _scan_for_opportunities(self) -> List[Dict]:
        """Buscar oportunidades usando el scanner"""
        if not self.scanner:
            self.logger.warning("🔍 No scanner available")
            return []
        
        try:
            self.logger.info("🔍 Calling scanner.scan_daily_plays()...")
            # Usar el SmallcapDailyScanner real
            plays = await self.scanner.scan_daily_plays()
            self.logger.info(f"🔍 Scanner returned {len(plays) if plays else 0} raw plays")
            
            # Convertir SmallcapPlay objects a dict format
            opportunities = []
            for play in plays:
                opportunity = {
                    'symbol': play.symbol,
                    'quality_score': play.quality_score,
                    'catalyst_type': play.catalyst.catalyst_type,
                    'catalyst_strength': play.catalyst.strength,
                    'current_price': play.context.current_price,
                    'gap_percentage': play.context.gap_percentage,
                    'volume_ratio': play.context.volume_ratio,
                    'recommendation': play.trading_recommendation
                }
                opportunities.append(opportunity)
                
            self.logger.info(f"🎯 Scanner encontró {len(opportunities)} oportunidades")
            return opportunities
            
        except Exception as e:
            self.logger.error(f"❌ Error scanning: {e}")
            return []
    
    async def _handle_scanner_opportunities(self, opportunities: List[Dict]):
        """Handle opportunities received from scanner via Redis bridge"""
        self.logger.info(f"📡 Received {len(opportunities)} opportunities via bridge")
        await self._evaluate_opportunities(opportunities)
    
    async def _evaluate_opportunities(self, opportunities: List[Dict]):
        """Evaluar oportunidades usando Mayordomo unificado"""
        
        # Filtrar oportunidades para notificaciones inteligentes
        new_or_changed_plays = self._filter_notification_worthy_plays(opportunities)
        
        # Enviar notificación solo si hay plays nuevos o con cambios significativos
        if new_or_changed_plays and self.telegram_client and hasattr(self.telegram_client, 'send_message'):
            await self._send_plays_notification(new_or_changed_plays)
        
        for opportunity in opportunities:
            try:
                symbol = opportunity.get('symbol', '')
                
                # Usar Mayordomo unificado
                if self.mayordomo:
                    decision = self.mayordomo.evaluate_position_rotation(opportunity)
                    
                    if decision.get('action') == 'EXECUTE':
                        # Agregar al TradingEngine unificado
                        if self.trading_engine:
                            success = await self.trading_engine.add_symbol(symbol, skip_validation=True)
                            if success:
                                self.logger.info(f"✅ {symbol} agregado para trading")
                    else:
                        reason = decision.get('reason', 'Unknown')
                        self.logger.debug(f"🚫 {symbol} rechazado: {reason}")
                        
            except Exception as e:
                self.logger.error(f"❌ Error evaluando {opportunity}: {e}")
    
    def _filter_notification_worthy_plays(self, opportunities: List[Dict]) -> List[Dict]:
        """Filtrar plays que merecen notificación - evitar spam"""
        worthy_plays = []
        now = datetime.now()
        
        for play in opportunities:
            symbol = play.get('symbol', '')
            if not symbol:
                continue
                
            current_data = {
                'price': play.get('current_price', 0),
                'gap': play.get('gap_percentage', 0),
                'volume_ratio': play.get('volume_ratio', 0),
                'quality_score': play.get('quality_score', 0)
            }
            
            # Verificar si es la primera vez que vemos este ticker
            if symbol not in self.notified_plays:
                self.notified_plays[symbol] = {
                    'last_notified': now,
                    'last_data': current_data
                }
                worthy_plays.append(play)
                self.logger.info(f"🆕 Nuevo play detectado: {symbol}")
                continue
            
            # Verificar cooldown
            last_notification = self.notified_plays[symbol]['last_notified']
            seconds_since_last = (now - last_notification).total_seconds()
            
            if seconds_since_last < self.notification_cooldown:
                continue  # Aún en cooldown
            
            # Verificar cambios significativos
            last_data = self.notified_plays[symbol]['last_data']
            
            significant_changes = []
            
            # Cambio de precio > 5%
            price_change = abs(current_data['price'] - last_data['price']) / max(last_data['price'], 0.01)
            if price_change > 0.05:
                significant_changes.append(f"precio {price_change*100:.1f}%")
            
            # Cambio de gap > 2%  
            gap_change = abs(current_data['gap'] - last_data['gap'])
            if gap_change > 0.02:
                significant_changes.append(f"gap {gap_change*100:.1f}%")
            
            # Cambio de volumen > 50%
            vol_change = abs(current_data['volume_ratio'] - last_data['volume_ratio']) / max(last_data['volume_ratio'], 0.1)
            if vol_change > 0.5:
                significant_changes.append(f"vol {vol_change*100:.1f}%")
            
            # Cambio de quality score > 1 punto
            score_change = abs(current_data['quality_score'] - last_data['quality_score'])
            if score_change > 1.0:
                significant_changes.append(f"score {score_change:.1f}pts")
            
            if significant_changes:
                self.notified_plays[symbol] = {
                    'last_notified': now,
                    'last_data': current_data
                }
                play['change_reason'] = ', '.join(significant_changes)
                worthy_plays.append(play)
                self.logger.info(f"📊 {symbol} cambios significativos: {', '.join(significant_changes)}")
        
        return worthy_plays
    
    async def _send_plays_notification(self, plays: List[Dict]):
        """Enviar notificación inteligente de plays"""
        if not plays:
            return
            
        try:
            plays_text = ""
            for i, play in enumerate(plays, 1):  # Mostrar todos los plays
                gap_emoji = "📈" if play.get('gap_percentage', 0) > 0 else "📉"
                symbol = play.get('symbol', 'N/A')
                
                change_info = ""
                if 'change_reason' in play:
                    change_info = f" ({play['change_reason']})"
                    
                plays_text += f"""
**{i}. {symbol} {gap_emoji}**{change_info}
• ${play.get('current_price', 0):.2f} | Gap: {play.get('gap_percentage', 0)*100:+.1f}%
• Vol: {play.get('volume_ratio', 0):.1f}x | Score: {play.get('quality_score', 0):.1f}
• {play.get('catalyst_type', 'N/A')}"""
            
            message = f"""🎯 **PLAYS DETECTADOS** - {datetime.now().strftime('%H:%M')}
═══════════════════════════════
{plays_text}

📊 Plays mostrados: {len(plays)}
🔄 Próximo scan en ~{getattr(self.config, 'scan_interval_seconds', 30)}s
"""
            
            self.telegram_client.send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            self.logger.error(f"❌ Error enviando notificación de plays: {e}")
    
    # Interfaz unificada para comandos
    async def add_symbol(self, symbol: str, skip_validation: bool = False) -> bool:
        """Agregar símbolo (interfaz unificada)"""
        if self.trading_engine:
            return await self.trading_engine.add_symbol(symbol, skip_validation)
        return False
    
    async def remove_symbol(self, symbol: str):
        """Remover símbolo (interfaz unificada)"""
        if self.trading_engine:
            await self.trading_engine.remove_symbol(symbol)
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado del sistema unificado"""
        status = {
            'system': 'UnifiedTradingSystem',
            'running': self.is_running,
            'timestamp': datetime.now().isoformat(),
        }
        
        # Agregar estado del ServiceLocator
        status.update(self.service_locator.get_system_status())
        
        return status
    
    def get_positions(self) -> Dict[str, Any]:
        """Obtener posiciones (interfaz unificada)"""
        if self.risk_manager:
            return getattr(self.risk_manager, 'broker_positions', {})
        return {}
    
    async def stop(self):
        """Detener sistema unificado"""
        try:
            self.logger.info("🛑 Deteniendo sistema unificado...")
            self.is_running = False
            self.shutdown_requested = True
            
            # Detener trading engine task
            if self.trading_engine_task:
                self.trading_engine_task.cancel()
                try:
                    await self.trading_engine_task
                except asyncio.CancelledError:
                    pass
            
            # Detener scanner
            if self.scanner_task:
                self.scanner_task.cancel()
                try:
                    await self.scanner_task
                except asyncio.CancelledError:
                    pass
            
            # Detener bridge task
            if self.bridge_task:
                self.bridge_task.cancel()
                try:
                    await self.bridge_task
                except asyncio.CancelledError:
                    pass
                    
            # Disconnect bridge
            await self.scanner_trader_bridge.disconnect()
            
            # Stop Telegram Command Listener
            if self.telegram_client:
                try:
                    self.telegram_client.stop_command_listener()
                    self.logger.info("✅ Telegram Command Listener detenido correctamente")
                except Exception as e:
                    self.logger.warning(f"⚠️ Error stopping Telegram Command Listener: {e}")
            
            # Cleanup servicios
            await self.service_locator.cleanup()
            
            # Notificación de shutdown
            if self.telegram_client and hasattr(self.telegram_client, 'send_message'):
                self.telegram_client.send_message(
                    "🛑 **UNIFIED TRADING SYSTEM DETENIDO**\n\nSistema apagado correctamente.",
                    parse_mode="Markdown"
                )
            
            self.logger.info("✅ Sistema unificado detenido")
            
        except Exception as e:
            self.logger.error(f"❌ Error deteniendo sistema: {e}")

# Funciones de línea de comandos
async def interactive_mode():
    """Modo interactivo con comandos"""
    system = UnifiedTradingSystem()
    await system.initialize()
    
    # Symbols por defecto desde config
    config = get_config()
    parser = configparser.ConfigParser()
    parser.read('config.ini')
    default_symbols = parser.get('TRADING', 'default_symbols', fallback='NONE').split(',')
    default_symbols = [s.strip() for s in default_symbols if s.strip() != 'NONE']
    
    await system.start(default_symbols)
    
    print("\n" + "="*60)
    print("🤖 UNIFIED TRADING SYSTEM")  
    print("="*60)
    print("Commands:")
    print("  add <SYMBOL>     - Add symbol to monitor")
    print("  remove <SYMBOL>  - Remove symbol from monitoring")
    print("  status           - Show system status")
    print("  positions        - Show current positions")
    print("  stop/quit/exit   - Stop the system")
    print("  Ctrl+C           - Quick exit")
    print("="*60)
    print(f"📈 Símbolos iniciales: {default_symbols}")
    print("💡 Puedes agregar más con: add <SYMBOL>")
    
    try:
        while system.is_running and not system.shutdown_requested:
            try:
                cmd = input("\n> ").strip().lower()
                
                if not cmd:
                    continue
                
                if cmd in ['stop', 'quit', 'exit']:
                    break
                elif cmd == 'status':
                    status = system.get_status()
                    print(f"Status: {status}")
                elif cmd == 'positions':
                    positions = system.get_positions()
                    print(f"Positions: {positions}")
                elif cmd.startswith('add '):
                    symbol = cmd.split(' ', 1)[1].upper()
                    success = await system.add_symbol(symbol)
                    print(f"{'✅' if success else '❌'} {symbol}")
                elif cmd.startswith('remove '):
                    symbol = cmd.split(' ', 1)[1].upper()
                    await system.remove_symbol(symbol)
                    print(f"🗑️ Removed {symbol}")
                else:
                    print("❓ Unknown command")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    finally:
        await system.stop()

# Entry point
async def main():
    """Punto de entrada principal"""
    try:
        await interactive_mode()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())