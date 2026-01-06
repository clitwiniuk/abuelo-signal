#!/usr/bin/env python3
"""
Independent Trader Process  
Receives opportunities from scanner via Redis and executes trades
"""

import asyncio
import logging
import signal
import sys
import os
from typing import List, Dict
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.service_locator import get_service_locator
from core.scanner_trader_bridge import ScannerTraderBridge
from core.notification_filter import NotificationFilter
from utils.log_config import setup_logging
# ML removed - using SimpleStrategyEngine instead

class IndependentTrader:
    """
    Independent trader process - runs separately from scanner
    """
    
    def __init__(self):
        setup_logging(level="INFO", log_file="logs/trader.log")
        self.logger = logging.getLogger("Trader")
        
        # Service locator for unified services
        self.service_locator = get_service_locator()
        self.config = None
        
        # Register self as unified_trading_system for Telegram compatibility
        self.service_locator.register_service('unified_trading_system', self)
        
        # Trading components (injected by ServiceLocator)
        self.ibkr_adapter = None
        self.trading_engine = None
        self.risk_manager = None
        self.mayordomo = None
        self.smart_game_plan_manager = None
        self.telegram_client = None
        self.tradetally_service = None

        # Swing trading components
        self.swing_scanner = None
        self.swing_worker = None
        self.swing_scheduler = None
        
        # ML REMOVED - SimpleStrategyEngine handles all strategy selection
        
        # Communication bridge
        self.bridge = ScannerTraderBridge()
        self.bridge_task = None
        self.trading_engine_task = None
        
        # Control
        self.is_running = False
        self.shutdown_requested = False

        # EOD OHLC Downloader task
        self.eod_ohlc_task = None
        self.last_eod_download_date = None
        self.last_pre_close_download_date = None  # For Phase 1 (previous day complete data)

        # Scanner plays storage for Telegram /plays_today command
        self.notified_plays = {}  # {symbol: {last_notified: datetime, last_data: dict}}
        
        # Sistema anti-spam para notificaciones
        self.notification_filter = NotificationFilter(
            cooldown_seconds=300,  # 5 minutos entre notificaciones del mismo símbolo
            logger=self.logger
        )
        
        self.logger.info("⚡ Independent Trader Process initialized")
        
    async def initialize(self):
        """Initialize trader components"""
        try:
            # Load unified configuration
            self.config = self.service_locator.load_config()
            self.logger.info(f"✅ Config loaded - Client ID: {self.config.client_id}")
            
            # Initialize all trading components via ServiceLocator
            self.logger.info("🔗 Getting IBKR adapter...")
            self.ibkr_adapter = await self.service_locator.get_or_create_ibkr_adapter()
            
            self.logger.info("🛡️ Getting risk manager...")
            self.risk_manager = await self.service_locator.get_or_create_risk_manager()

            # LEGACY: Mayordomo not needed in worker-based system
            # self.logger.info("🏛️ Getting mayordomo...")
            # self.mayordomo = await self.service_locator.get_or_create_mayordomo()

            # LEGACY: SmartGamePlanManager not needed in worker-based system
            # self.logger.info("🧠 Getting smart game plan manager...")
            # self.smart_game_plan_manager = await self.service_locator.get_or_create_smart_game_plan_manager()
            
            self.logger.info("📱 Getting telegram client...")
            self.telegram_client = self.service_locator.get_or_create_telegram_client()
            
            # Initialize TradeTally service
            self.logger.info("📊 Getting TradeTally service...")
            self.tradetally_service = await self.service_locator.get_or_create_tradetally_service()
            
            # Start Telegram command listener only in trader process (avoid multiple instances)
            try:
                from notifications.telegram_client import start_command_listener, is_enabled
                if is_enabled():
                    if start_command_listener():
                        self.logger.info("✅ Telegram command listener started successfully")
                    else:
                        self.logger.warning("⚠️ Failed to start Telegram command listener")
            except Exception as e:
                self.logger.error(f"❌ Error starting Telegram listener: {e}")
            
            # LEGACY TRADING ENGINE DISABLED - Using Worker-Based System Only
            # The legacy trading engine has been replaced by the worker-based architecture
            # Workers handle all trading logic now
            self.logger.info("⚡ Legacy trading engine DISABLED - using worker-based system only")

            # Get broker and risk_manager directly (no need for old TradingEngine)
            self.logger.info("🔗 Getting shared services for workers...")
            ibkr_adapter = await self.service_locator.get_or_create_ibkr_adapter()
            risk_manager = await self.service_locator.get_or_create_risk_manager()

            if ibkr_adapter is None or risk_manager is None:
                self.logger.error("❌ Failed to initialize broker or risk manager!")
                return False

            self.logger.info("✅ All services initialized successfully")

            # WORKER-BASED ARCHITECTURE - Parallel strategy evaluation
            self.logger.info("🎯 Initializing Worker-Based Strategy Engine...")
            from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine
            from core.execution_engine_adapter import ExecutionEngineAdapter

            # Create execution adapter with direct broker/risk_manager injection (new mode)
            execution_adapter = ExecutionEngineAdapter(
                broker=ibkr_adapter,
                risk_manager=risk_manager,
                config=self.config
            )

            # Register restored positions with UnifiedPositionManager (async)
            await execution_adapter.register_restored_positions_with_unified_manager()

            self.strategy_engine = WorkerBasedStrategyEngine(
                execution_engine=execution_adapter,
                risk_manager=self.risk_manager
            )

            await self.strategy_engine.initialize()
            await self.strategy_engine.start()

            self.logger.info("✅ Worker-Based Strategy Engine started")

            # ADAPTIVE MARKET REGIME SYSTEM - Initialize regime detector
            self.logger.info("🌍 Initializing Adaptive Market Regime System...")
            try:
                from core.market_regime_detector import get_market_regime_detector
                regime_detector = get_market_regime_detector()
                regime_detector.set_ibkr_adapter(ibkr_adapter)
                await regime_detector.start()
                self.logger.info("✅ Market regime detector started (updates every 15min)")

                # Initial regime detection
                await regime_detector.update_market_regime()

                # Log initial regime
                from core.adaptive_threshold_manager import get_adaptive_threshold_manager
                threshold_mgr = get_adaptive_threshold_manager()
                regime_summary = threshold_mgr.get_regime_summary()
                self.logger.info(f"📊 Initial Market Regime: {regime_summary.get('regime', 'UNKNOWN').upper()}")
                self.logger.info(f"   SPY Trend: {regime_summary.get('spy_trend', 'N/A')}, Liquidity: {regime_summary.get('liquidity', 'N/A')}")
                self.logger.info(f"   Entries Allowed: {regime_summary.get('entries_allowed', True)}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not initialize adaptive regime system: {e}")
                self.logger.warning("   System will use fallback Friday-only adaptation")

            # Send startup notification to Telegram
            self.logger.info(f"🔍 DEBUG: telegram_client exists: {self.telegram_client is not None}")
            if self.telegram_client:
                self.logger.info("🔍 DEBUG: Attempting to send startup notification...")
                try:
                    from notifications.telegram_client import send_message
                    self.logger.info("🔍 DEBUG: send_message imported, calling it now...")
                    send_message("🚀 Trading system iniciado y en funcionamiento ✅")
                    self.logger.info("📨 Startup notification sent to Telegram")
                except Exception as e:
                    self.logger.warning(f"Failed to send startup notification: {e}")
                    import traceback
                    self.logger.warning(f"Traceback: {traceback.format_exc()}")
            else:
                self.logger.warning("⚠️ telegram_client is None, cannot send startup notification")

            # SWING TRADING SYSTEM - Initialize swing components
            self.logger.info("🏛️ Initializing Swing Trading System...")
            try:
                self.logger.info("   🔍 Importing swing components...")
                from scanner.swing.swing_consolidation_scanner import SwingConsolidationScanner
                from strategies.swing_workers.consolidation_breakout_worker import ConsolidationBreakoutWorker
                from core.swing_scheduler import SwingScheduler
                self.logger.info("   ✅ Swing components imported successfully")

                # Verify IBKR adapter availability
                if ibkr_adapter is None:
                    raise Exception("IBKR adapter not available for swing scanner")

                self.logger.info("   🔍 Creating swing scanner...")
                self.swing_scanner = SwingConsolidationScanner(
                    ibkr_adapter=ibkr_adapter,
                    config_path="config.ini"
                )
                self.logger.info("   ✅ Swing scanner created")

                self.logger.info("   🔍 Creating swing worker...")
                self.swing_worker = ConsolidationBreakoutWorker(
                    execution_engine=execution_adapter,
                    risk_manager=risk_manager,
                    config=self.config
                )
                self.logger.info("   ✅ Swing worker created")

                self.logger.info("   🔍 Creating swing scheduler...")
                self.swing_scheduler = SwingScheduler(
                    scanner=self.swing_scanner,
                    worker=self.swing_worker,
                    logger=self.logger
                )
                self.logger.info("   ✅ Swing scheduler created")

                self.logger.info("   ▶️ Starting swing scheduler...")
                await self.swing_scheduler.start()
                self.logger.info("   ✅ Swing scheduler started")

                self.logger.info("✅ Swing Trading System initialized and started")
                self.logger.info("   📅 EOD scan: 15:40 ET (21:40 España)")
                self.logger.info("   🔔 Market open: 9:30 ET (BREAKOUT mode)")
                self.logger.info("   📊 Intraday monitor: Every 5 min (PULLBACK mode)")

            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Swing Trading System: {e}")
                import traceback
                self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
                # Continue without swing trading
                self.logger.warning("⚠️ Continuing without swing trading functionality")

            # Connect to Redis bridge
            bridge_connected = await self.bridge.connect()
            if not bridge_connected:
                self.logger.warning("⚠️ Redis not available - trader will run without scanner communication")
                self.logger.warning("   Install redis-py to enable scanner-trader bridge: pip install redis")
            else:
                self.logger.info("✅ Redis bridge connected - scanner communication enabled")

            self.logger.info("✅ Trader fully initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Trader initialization failed: {e}")
            import traceback
            self.logger.error(f"❌ Full stack trace: {traceback.format_exc()}")
            return False
    
    async def start(self):
        """Start independent trader process"""
        if not await self.initialize():
            return False
            
        self.logger.info("🚀 Starting independent trader process...")
        self.is_running = True
        
        # Setup signal handlers
        def signal_handler(signum, _frame):
            self.logger.info(f"📡 Signal {signum} received - shutting down trader")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start bridge subscriber (listen for scanner opportunities)
        if self.bridge.redis_client:
            self.bridge_task = asyncio.create_task(
                self.bridge.subscribe_to_opportunities(self._handle_scanner_opportunities)
            )
            self.logger.info("✅ Listening for scanner opportunities via Redis")
        
        # LEGACY TRADING ENGINE NOT STARTED - Workers handle all trading
        # The trading engine object exists for ExecutionEngineAdapter compatibility
        # but we don't start it as a monitoring task
        if self.trading_engine:
            self.logger.info("ℹ️  Legacy trading engine NOT started - workers handle all trading")
            self.trading_engine_task = None  # No legacy monitoring task
        
        # Start EOD OHLC downloader task
        self.eod_ohlc_task = asyncio.create_task(self._eod_ohlc_scheduler())

        # Keep trader alive - just wait for opportunities
        try:
            while self.is_running and not self.shutdown_requested:
                await asyncio.sleep(5)  # Heartbeat every 5 seconds

        except KeyboardInterrupt:
            self.logger.info("🛑 Trader interrupted by user")

        await self.stop()
        self.logger.info("🛑 Trader process stopped")
        return True

    async def _eod_ohlc_scheduler(self):
        """
        Automatic EOD OHLC downloader with TWO PHASES:

        🏃 PHASE 1 (Pre-open): 2 min before market open (15:28 Spain) - Download COMPLETE data for previous day
                               (premarket + regular + afterhours for yesterday's trades)

        🌙 PHASE 2 (Post-close): At 22:00 Spanish time - Download COMPLETE data for current day
                                (premarket + regular + afterhours for today's trades)
        """
        self.logger.info("📊 EOD OHLC scheduler started - TWO PHASE SYSTEM")
        self.logger.info("   🏃 Phase 1: Pre-open (15:28 Spain) - Previous day complete data")
        self.logger.info("   🌙 Phase 2: Post-close (22:00 Spain) - Current day complete data")

        while self.is_running and not self.shutdown_requested:
            try:
                from datetime import datetime, time, timedelta
                import pytz

                # Get current time in Spanish timezone
                spanish_tz = pytz.timezone('Europe/Madrid')
                now = datetime.now(spanish_tz)
                today_date = now.date()

                # PHASE 1: Pre-open execution (2 min before market open) - Download previous day complete data
                pre_open_target = time(15, 28)  # 15:28 Spanish time (2 min before 15:30 market open)
                pre_open_datetime = datetime.combine(today_date, pre_open_target)
                pre_open_datetime = spanish_tz.localize(pre_open_datetime)

                # PHASE 2: Post-close execution (22:00) - Download current day complete data
                post_close_target = time(22, 0)  # 22:00 Spanish time
                post_close_datetime = datetime.combine(today_date, post_close_target)
                post_close_datetime = spanish_tz.localize(post_close_datetime)

                # Check PHASE 1: Pre-open (previous day complete data)
                phase1_should_run = False
                if (now.time() >= pre_open_target and now.time() < post_close_target and
                    self.last_pre_close_download_date != today_date):
                    phase1_should_run = True
                    self.logger.info(f"🎯 PHASE 1: Pre-open download triggered! (now: {now.strftime('%H:%M')})")

                # Check PHASE 2: Post-close (current day complete data)
                phase2_should_run = False
                if now.time() >= post_close_target and self.last_eod_download_date != today_date:
                    phase2_should_run = True
                    self.logger.info(f"🎯 PHASE 2: Post-close download triggered! (now: {now.strftime('%H:%M')})")

                # Execute PHASE 1: Download previous day complete data
                if phase1_should_run:
                    await self._execute_phase_download(
                        phase_name="PHASE 1 (Pre-close)",
                        target_date=(today_date - timedelta(days=1)).isoformat(),
                        description="Previous day complete data (premarket + regular + afterhours)"
                    )
                    self.last_pre_close_download_date = today_date

                # Execute PHASE 2: Download current day complete data
                if phase2_should_run:
                    await self._execute_phase_download(
                        phase_name="PHASE 2 (Post-close)",
                        target_date=today_date.isoformat(),
                        description="Current day complete data (premarket + regular + afterhours)"
                    )
                    self.last_eod_download_date = today_date

                # Check every 5 minutes
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                self.logger.info("📊 EOD OHLC scheduler cancelled")
                break
            except Exception as e:
                self.logger.error(f"❌ Error in EOD OHLC scheduler: {e}")
                await asyncio.sleep(300)  # Wait 5 min before retry

    async def _execute_phase_download(self, phase_name: str, target_date: str, description: str):
        """
        Execute download for a specific phase
        """
        self.logger.info(f"📥 {phase_name}: Starting download - {description}")
        self.logger.info(f"🎯 Target date: {target_date}")

        try:
            # Import and run the downloader with specific date
            from scripts.maintenance.download_eod_ohlc import EODOHLCDownloader

            # Create downloader for specific date
            downloader = EODOHLCDownloader(target_date=target_date)
            success = await downloader.run()

            if success:
                self.logger.info(f"✅ {phase_name} download completed successfully for {target_date}")

                # Send Telegram notification
                try:
                    from notifications.telegram_client import send_message
                    send_message(f"📊 {phase_name} OHLC data downloaded for {target_date}")
                except Exception as e:
                    self.logger.debug(f"Telegram notification skipped: {e}")
            else:
                self.logger.warning(f"⚠️ {phase_name} download completed with errors for {target_date}")

        except Exception as e:
            self.logger.error(f"❌ {phase_name} download failed for {target_date}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def _handle_scanner_opportunities(self, opportunities: List[Dict]):
        """Handle opportunities received from scanner via Redis"""
        try:
            from datetime import datetime
            self.logger.info(f"📡 Received {len(opportunities)} opportunities from scanner")

            # ========================================
            # CRITICAL: AUTO-SUBSCRIBE TO TICKERS
            # ========================================
            # Subscribe to tickers IMMEDIATELY when opportunities arrive
            # This ensures fresh prices (< 1 second) are available for validation
            symbols_to_subscribe = []
            for opportunity in opportunities:
                if opportunity.get('needs_subscription', False):
                    symbol = opportunity.get('symbol', '')
                    if symbol:
                        symbols_to_subscribe.append(symbol)

            if symbols_to_subscribe and hasattr(self.ibkr_adapter, 'batch_price_manager') and self.ibkr_adapter.batch_price_manager:
                self.logger.info(f"📡 Auto-subscribing to {len(symbols_to_subscribe)} tickers for fresh prices")
                try:
                    subscription_results = await self.ibkr_adapter.batch_price_manager.subscribe_to_positions(symbols_to_subscribe)
                    successful = sum(1 for success in subscription_results.values() if success)
                    self.logger.info(f"✅ Subscribed to {successful}/{len(symbols_to_subscribe)} tickers successfully")

                    # Give a moment for initial price data to arrive
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.logger.error(f"❌ Failed to auto-subscribe to tickers: {e}")

            # Store all scanner opportunities in database
            await self._store_scanner_opportunities(opportunities)

            # Store all plays for /plays_today command
            now = datetime.now()

            # ========================================
            # WORKER-BASED ARCHITECTURE - NEW APPROACH
            # ========================================
            # Delegate opportunities to workers for parallel evaluation
            self.logger.info(f"🎯 Checking strategy engine: hasattr={hasattr(self, 'strategy_engine')}, exists={getattr(self, 'strategy_engine', None) is not None}")
            if hasattr(self, 'strategy_engine') and self.strategy_engine:
                self.logger.info("✅ Using Worker-Based Strategy Engine")
                for opportunity in opportunities:
                    symbol = opportunity.get('symbol', '')

                    # Prepare current data for notification filter
                    current_data = {
                        'price': opportunity.get('current_price', 0.0),
                        'gap': opportunity.get('gap_percentage', 0.0),
                        'volume_ratio': opportunity.get('volume_ratio', 0.0),
                        'quality_score': opportunity.get('quality_score', 0.0)
                    }

                    # Store for Telegram /plays_today
                    self.notified_plays[symbol] = {
                        'last_notified': now,
                        'last_data': {
                            'symbol': symbol,
                            'price': current_data['price'],
                            'gap': current_data['gap'],
                            'volume_ratio': current_data['volume_ratio'],
                            'quality_score': current_data['quality_score'],
                            'catalyst_type': opportunity.get('catalyst_type', 'N/A')
                        }
                    }

                    # DEBUG: Log opportunity details
                    self.logger.info(
                        f"🔍 DEBUG Opportunity {symbol}: "
                        f"gap={opportunity.get('gap_percentage', 0):.1f}%, "
                        f"vol={opportunity.get('volume_ratio', 0):.1f}x, "
                        f"catalyst={opportunity.get('catalyst_type', 'N/A')}, "
                        f"catalyst_strength={opportunity.get('catalyst_strength', 0)}, "
                        f"price=${opportunity.get('current_price', 0):.2f}, "
                        f"Q={opportunity.get('quality_score', 0):.1f}"
                    )

                    # Check if should notify using anti-spam filter
                    should_notify, notification_reason = self.notification_filter.should_notify(symbol, current_data)

                    # Send Telegram notification if passes anti-spam filter
                    if should_notify:
                        try:
                            from notifications.telegram_client import send_message, is_enabled
                            if is_enabled():
                                stored_data = self.notified_plays[symbol]['last_data']
                                play_msg = f"📊 **DAILY PLAY DETECTED**\n\n"
                                play_msg += f"**Symbol:** {symbol}\n"
                                play_msg += f"**Quality Score:** {stored_data['quality_score']:.1f}\n"
                                play_msg += f"**Catalyst:** {stored_data['catalyst_type']}\n"
                                play_msg += f"**Price:** ${stored_data['price']:.2f}\n"
                                play_msg += f"**Gap:** {stored_data['gap']:.1f}%\n"
                                play_msg += f"**Volume Ratio:** {stored_data['volume_ratio']:.1f}x\n"
                                play_msg += f"**Time:** {now.strftime('%H:%M:%S')}\n"
                                play_msg += f"**Razón:** {notification_reason}"
                                send_message(play_msg, parse_mode="Markdown")
                                self.logger.info(f"📱 Sent daily play notification for {symbol}: {notification_reason}")
                        except Exception as e:
                            self.logger.error(f"❌ Failed to send Telegram notification for {symbol}: {e}")
                    else:
                        self.logger.debug(f"🔇 Notification skipped for {symbol}: {notification_reason}")

                    # ENHANCED: Route by strategy_targets for specific worker delegation
                    strategy_targets = opportunity.get('strategy_targets', [])
                    self.logger.info(f"🎯 Routing {symbol} by strategy_targets: {strategy_targets}")

                    # Route to specific workers based on strategy_targets
                    routed = False
                    if 'gap_go' in strategy_targets:
                        if hasattr(self.strategy_engine, 'gap_go_worker'):
                            await self.strategy_engine.gap_go_worker.process_opportunity(opportunity)
                            routed = True
                            self.logger.info(f"✅ {symbol} routed to Gap-Go worker")
                    elif 'bull_flag' in strategy_targets:
                        if hasattr(self.strategy_engine, 'bull_flag_worker'):
                            await self.strategy_engine.bull_flag_worker.process_opportunity(opportunity)
                            routed = True
                            self.logger.info(f"✅ {symbol} routed to Bull Flag worker")
                    elif 'macdv_smallcaps' in strategy_targets:
                        if hasattr(self.strategy_engine, 'macdv_worker'):
                            await self.strategy_engine.macdv_worker.process_opportunity(opportunity)
                            routed = True
                            self.logger.info(f"✅ {symbol} routed to MACDV worker")
                    elif 'daily_plays' in strategy_targets:
                        if hasattr(self.strategy_engine, 'daily_plays_worker'):
                            await self.strategy_engine.daily_plays_worker.process_opportunity(opportunity)
                            routed = True
                            self.logger.info(f"✅ {symbol} routed to Daily Plays worker")
                    elif 'volume_absorption' in strategy_targets:
                        if hasattr(self.strategy_engine, 'volume_absorption_worker'):
                            await self.strategy_engine.volume_absorption_worker.process_opportunity(opportunity)
                            routed = True
                            self.logger.info(f"✅ {symbol} routed to Volume Absorption worker")

                    # Fallback to generic processing if no specific routing
                    if not routed:
                        self.logger.info(f"🎯 {symbol} using generic worker processing")
                        await self.strategy_engine.process_opportunity(opportunity)

                    self.logger.info(f"✅ Worker processing completed for {symbol}")

                self.logger.info("🎯 Worker-based architecture: opportunities processed")
                # DON'T EXIT main loop - Let workers continue monitoring until EOD
                # Workers will handle EOD closure at configured time (15:58)
                # But DO exit this handler to avoid falling into legacy path
                return

            # ========================================
            # FALLBACK - OLD APPROACH (if workers not available)
            # ========================================
            self.logger.warning("⚠️ WorkerBasedEngine not available, using legacy path")

            # Evaluate each opportunity using legacy path
            for opportunity in opportunities:
                try:
                    symbol = opportunity.get('symbol', '')
                    quality_score = opportunity.get('quality_score', 0.0)
                    opportunity_type = opportunity.get('opportunity_type', 'UNKNOWN')
                    
                    # Preparar datos para filtro anti-spam y almacenar para /plays_today
                    current_data = {
                        'price': opportunity.get('current_price', 0.0),
                        'gap': opportunity.get('gap_percentage', 0.0),
                        'volume_ratio': opportunity.get('volume_ratio', 0.0),
                        'quality_score': quality_score
                    }
                    
                    # Store play in notified_plays for Telegram /plays_today command (siempre actualizar)
                    self.notified_plays[symbol] = {
                        'last_notified': now,
                        'last_data': {
                            'symbol': symbol,
                            'price': current_data['price'],
                            'gap': current_data['gap'],
                            'volume_ratio': current_data['volume_ratio'],
                            'quality_score': current_data['quality_score'],
                            'catalyst_type': opportunity.get('catalyst_type', 'N/A')
                        }
                    }
                    
                    # Verificar si merece notificación usando filtro anti-spam
                    should_notify, notification_reason = self.notification_filter.should_notify(symbol, current_data)
                    
                    # Send Telegram notification solo si pasa el filtro anti-spam
                    if should_notify:
                        try:
                            from notifications.telegram_client import send_message, is_enabled
                            if is_enabled():
                                # Usar los datos almacenados para consistencia con /plays_today
                                stored_data = self.notified_plays[symbol]['last_data']
                                play_msg = f"📊 **DAILY PLAY DETECTED**\n\n"
                                play_msg += f"**Symbol:** {symbol}\n"
                                play_msg += f"**Quality Score:** {stored_data['quality_score']:.1f}\n"
                                play_msg += f"**Catalyst:** {stored_data['catalyst_type']}\n"
                                play_msg += f"**Price:** ${stored_data['price']:.2f}\n"
                                play_msg += f"**Gap:** {stored_data['gap']:.1f}%\n"
                                play_msg += f"**Volume Ratio:** {stored_data['volume_ratio']:.1f}x\n"
                                play_msg += f"**Time:** {now.strftime('%H:%M:%S')}\n"
                                play_msg += f"**Razón:** {notification_reason}"
                                send_message(play_msg, parse_mode="Markdown")
                                self.logger.info(f"📱 Sent daily play notification for {symbol}: {notification_reason}")
                        except Exception as e:
                            self.logger.error(f"❌ Failed to send Telegram notification for {symbol}: {e}")
                    else:
                        self.logger.debug(f"🔇 Notification skipped for {symbol}: {notification_reason}")
                    
                    self.logger.info(f"🔍 Evaluating {symbol} ({opportunity_type}, quality: {quality_score:.1f})")
                    
                    # FIRST: Add opportunity to Smart Game Plan Manager if not present
                    if self.smart_game_plan_manager:
                        try:
                            # Check if symbol is in current plan
                            if symbol not in self.smart_game_plan_manager.current_plan:
                                self.logger.info(f"🧠 Adding {symbol} to Smart Game Plan...")
                                # Use the strategy selection to add to plan
                                strategy, confidence = self.smart_game_plan_manager._select_optimal_strategy_with_context(opportunity)
                                
                                # Create game plan entry for new opportunity
                                from core.smart_game_plan_manager import SmartGamePlanEntry, MarketPhase, MarketSentiment
                                from datetime import datetime
                                
                                entry = SmartGamePlanEntry(
                                    symbol=symbol,
                                    tier='A',  # Default tier
                                    primary_strategy=strategy,
                                    primary_strategy_confidence=confidence,
                                    backup_strategies=[],
                                    strategy_selection_reasoning=f"Scanner detected: {opportunity.get('catalyst_type', 'N/A')}",
                                    entry_price=opportunity.get('current_price', 0.0),
                                    stop_loss=opportunity.get('current_price', 0.0) * 0.97,  # 3% stop
                                    target_1=opportunity.get('current_price', 0.0) * 1.06,   # 6% target
                                    target_2=opportunity.get('current_price', 0.0) * 1.10,   # 10% target
                                    technical_setup_score=quality_score,
                                    optimal_market_phases=[MarketPhase.OPENING, MarketPhase.AFTERNOON, MarketPhase.POWER_HOUR],
                                    required_sentiment=[MarketSentiment.NEUTRAL, MarketSentiment.BULLISH],
                                    min_volatility_regime='NORMAL',
                                    context_match_score=confidence,
                                    position_size=500,  # Default size
                                    max_risk_per_trade=1000,
                                    execution_urgency='MEDIUM',
                                    time_decay_factor=1.0,
                                    last_updated=datetime.now()
                                )
                                
                                # Add to current plan
                                self.smart_game_plan_manager.current_plan[symbol] = entry
                                
                                # Clear any cached decision for fresh evaluation
                                self.smart_game_plan_manager.clear_decision_cache(symbol)
                                
                                self.logger.info(f"✅ {symbol} added to Smart Game Plan with {strategy.value} strategy (conf: {confidence:.2f})")
                                
                        except Exception as e:
                            self.logger.warning(f"⚠️ Failed to add {symbol} to Smart Game Plan: {e}")
                    
                    # SECOND: Use appropriate decision logic based on opportunity type
                    execute_decision = False
                    decision_reason = "No decision system available"

                    # ROUTE BY OPPORTUNITY TYPE
                    if opportunity_type == 'FIRST_DAY_BOUNCE':
                        # Handle bounce setups with specialized logic
                        execute_decision, decision_reason = self._handle_bounce_opportunity(symbol, opportunity)

                    elif opportunity_type == 'INTRADAY_MOMENTUM':
                        # Handle intraday momentum with Smart Game Plan Manager
                        if self.smart_game_plan_manager:
                            try:
                                game_plan_decision = self.smart_game_plan_manager.get_instant_decision(symbol, opportunity, use_cache=False)

                                if game_plan_decision.get('action') == 'EXECUTE':
                                    self.logger.info(f"🧠 Smart Game Plan approved {symbol}: {game_plan_decision.get('reason', '')}")
                                    execute_decision = True
                                    decision_reason = f"Smart Game Plan: {game_plan_decision.get('reason', '')}"
                                else:
                                    self.logger.info(f"🧠 Smart Game Plan rejected {symbol}: {game_plan_decision.get('reason', '')}")
                                    execute_decision = False
                                    decision_reason = f"Smart Game Plan: {game_plan_decision.get('reason', '')}"
                            except Exception as e:
                                self.logger.warning(f"⚠️ Smart Game Plan Manager error for {symbol}: {e}")
                                execute_decision = None

                        # FALLBACK: Use Mayordomo for intraday if Smart Game Plan fails
                        if execute_decision is None and self.mayordomo:
                            self.logger.info(f"🏛️ Falling back to Mayordomo evaluation for {symbol}")
                            decision = self.mayordomo.evaluate_position_rotation(opportunity)
                            execute_decision = decision.get('action') == 'EXECUTE'
                            decision_reason = f"Mayordomo: {decision.get('reason', '')}"

                    else:
                        # UNKNOWN/DEFAULT: Use Smart Game Plan Manager as fallback
                        self.logger.warning(f"⚠️ Unknown opportunity type '{opportunity_type}' for {symbol}, using default logic")
                        if self.smart_game_plan_manager:
                            try:
                                game_plan_decision = self.smart_game_plan_manager.get_instant_decision(symbol, opportunity, use_cache=False)
                                execute_decision = game_plan_decision.get('action') == 'EXECUTE'
                                decision_reason = f"Smart Game Plan (default): {game_plan_decision.get('reason', '')}"
                            except Exception as e:
                                self.logger.warning(f"⚠️ Default decision failed for {symbol}: {e}")
                                execute_decision = False
                                decision_reason = f"Default decision failed: {e}"
                    
                    # Execute the decision
                    if execute_decision:
                        # Add to trading engine
                        if self.trading_engine:
                            success = await self.trading_engine.add_symbol(symbol, skip_validation=True)
                            if success:
                                self.logger.info(f"✅ {symbol} added for trading - {decision_reason}")
                            else:
                                self.logger.warning(f"⚠️ Failed to add {symbol} to trading engine")
                        else:
                            self.logger.warning("⚠️ No trading engine available")
                    else:
                        self.logger.info(f"🚫 {symbol} rejected: {decision_reason}")
                        
                except Exception as e:
                    self.logger.error(f"❌ Error processing opportunity {opportunity.get('symbol', 'UNKNOWN')}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"❌ Error handling scanner opportunities: {e}")

    def _handle_bounce_opportunity(self, symbol: str, opportunity: Dict) -> tuple[bool, str]:
        """
        Handle First Day Bounce opportunity with specialized logic

        Returns: (execute_decision, decision_reason)
        """
        try:
            bounce_metadata = opportunity.get('bounce_metadata', {})
            current_price = opportunity.get('current_price', 0.0)
            quality_score = opportunity.get('quality_score', 0.0)

            # 1. QUALITY THRESHOLD for bounce setups (relaxed)
            if quality_score < 55:  # Reduced from 70 to 55
                return False, f"Bounce quality too low: {quality_score:.1f} (need 55+)"

            # 2. RISK/REWARD VALIDATION (relaxed)
            risk_reward = bounce_metadata.get('risk_reward_ratio', 0)
            if risk_reward < 1.5:  # Reduced from 2.0 to 1.5
                return False, f"Poor risk/reward: {risk_reward:.1f} (need 1.5+)"

            # 3. SUPPORT PROXIMITY CHECK
            support_level = bounce_metadata.get('support_level', 0)
            if support_level > 0:
                distance_from_support = abs(current_price - support_level) / support_level
                if distance_from_support > 0.05:  # More than 5% from support
                    return False, f"Too far from support: {distance_from_support*100:.1f}% (need <5%)"

            # 4. RED DAYS VALIDATION (relaxed)
            red_days = bounce_metadata.get('red_days_count', 0)
            if red_days < 1 or red_days > 7:  # Relaxed: 1-7 days (was 2-5)
                return False, f"Red days count inappropriate: {red_days} (need 1-7)"

            # 5. OVEREXTENSION VALIDATION (relaxed)
            overextension_gain = bounce_metadata.get('overextension_gain_pct', 0)
            if overextension_gain < 0.25:  # Reduced from 40% to 25% overextension
                return False, f"Insufficient overextension: {overextension_gain*100:.1f}% (need 25%+)"

            # 6. RETRACE VALIDATION (relaxed)
            retrace_pct = bounce_metadata.get('retrace_pct', 0)
            if retrace_pct < 0.20 or retrace_pct > 0.65:  # Relaxed: 20-65% (was 25-50%)
                return False, f"Retrace out of range: {retrace_pct*100:.1f}% (need 20-65%)"

            # 7. MARKET PHASE CHECK (avoid premarket/afterhours for bounces)
            from datetime import datetime
            import pytz
            ny_tz = pytz.timezone('US/Eastern')
            current_time = datetime.now(ny_tz).time()

            if current_time < datetime.strptime("09:30", "%H:%M").time():
                return False, "Bounce setups not allowed in premarket"

            if current_time > datetime.strptime("16:00", "%H:%M").time():
                return False, "Bounce setups not allowed in afterhours"

            # 8. ALL CHECKS PASSED - APPROVE BOUNCE SETUP
            reason = (f"Bounce setup approved - Quality: {quality_score:.0f}, "
                     f"R/R: {risk_reward:.1f}, Overext: {overextension_gain*100:.1f}%, "
                     f"Retrace: {retrace_pct*100:.1f}%, Red days: {red_days}")

            self.logger.info(f"🎯 {symbol}: {reason}")
            return True, reason

        except Exception as e:
            self.logger.error(f"❌ Error handling bounce opportunity for {symbol}: {e}")
            return False, f"Bounce evaluation error: {e}"

    async def _store_scanner_opportunities(self, opportunities: List[Dict]):
        """Store all opportunities detected by scanner in database"""
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path("trading_data.db")
            stored_count = 0

            with sqlite3.connect(db_path) as conn:
                for opp in opportunities:
                    try:
                        conn.execute("""
                            INSERT INTO scanner_opportunities
                            (symbol, current_price, gap_percentage, volume_ratio,
                             quality_score, catalyst_type, catalyst_strength, opportunity_type,
                             recent_high_5d, recent_low_5d, volume_trend, price_momentum,
                             market_context, trade_session)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            opp.get('symbol'),
                            opp.get('current_price'),
                            opp.get('gap_percentage'),
                            opp.get('volume_ratio'),
                            opp.get('quality_score'),
                            opp.get('catalyst_type'),
                            opp.get('catalyst_strength'),
                            opp.get('opportunity_type'),
                            opp.get('recent_high_5d'),
                            opp.get('recent_low_5d'),
                            opp.get('volume_trend'),
                            opp.get('price_momentum'),
                            opp.get('market_context'),
                            opp.get('trade_session')
                        ))
                        stored_count += 1
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to store opportunity {opp.get('symbol')}: {e}")

                conn.commit()

            self.logger.info(f"💾 Stored {stored_count}/{len(opportunities)} scanner opportunities")

        except Exception as e:
            self.logger.error(f"❌ Failed to store scanner opportunities: {e}")

    async def stop(self):
        """Stop trader process"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            # Send shutdown notification to Telegram
            if self.telegram_client:
                try:
                    from notifications.telegram_client import send_message
                    send_message("🛑 Trading system detenido")
                    self.logger.info("📨 Shutdown notification sent to Telegram")
                except Exception as e:
                    self.logger.warning(f"Failed to send shutdown notification: {e}")

            # Stop swing scheduler
            if self.swing_scheduler:
                self.logger.info("🏛️ Stopping swing scheduler...")
                await self.swing_scheduler.stop()
                self.logger.info("✅ Swing scheduler stopped")

            # Stop EOD OHLC downloader task
            if self.eod_ohlc_task:
                self.logger.info("📊 Stopping EOD OHLC scheduler...")
                self.eod_ohlc_task.cancel()
                try:
                    await self.eod_ohlc_task
                except asyncio.CancelledError:
                    pass
                self.logger.info("✅ EOD OHLC scheduler stopped")

            # Stop bridge task
            if self.bridge_task:
                self.bridge_task.cancel()
                try:
                    await self.bridge_task
                except asyncio.CancelledError:
                    pass

            # Stop trading engine task
            if self.trading_engine_task:
                self.trading_engine_task.cancel()
                try:
                    await self.trading_engine_task
                except asyncio.CancelledError:
                    pass

            # Cleanup services
            await self.service_locator.cleanup()
            self.logger.info("✅ Service locator cleaned up")

            # Disconnect bridge
            await self.bridge.disconnect()
            self.logger.info("✅ Redis bridge disconnected")

        except Exception as e:
            self.logger.error(f"❌ Error stopping trader: {e}")
    
    async def _load_historical_trades_for_ml(self):
        """DEPRECATED - ML REMOVED - No longer needed"""
        self.logger.info("🚫 ML historical loading disabled - using SimpleStrategyEngine")
        return
    
    async def _provide_ml_feedback_on_trade(self, symbol: str, strategy: str, pnl: float, entry_price: float, quantity: int):
        """DEPRECATED - ML REMOVED - No feedback needed"""
        self.logger.debug(f"🚫 ML feedback disabled - {symbol} {strategy} PnL={pnl:.2f}")
        return  # ML completely removed

async def main():
    """Main function for independent trader"""
    trader = IndependentTrader()
    
    print("⚡ INDEPENDENT TRADER PROCESS")
    print("   ✅ Full trading engine")
    print("   ✅ Redis sub for opportunities")
    print("   ✅ Independent of scanner")
    print()
    
    try:
        success = await trader.start()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\\n🛑 Trader interrupted by user")
        await trader.stop()
        return 0
    except Exception as e:
        print(f"❌ Trader failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)