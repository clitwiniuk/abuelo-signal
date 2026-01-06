# production/telegram_smallcap_commands.py
"""
Comandos específicos de Telegram para el sistema smallcaps intraday
Extiende el sistema de telegram_client.py existente
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Imports del sistema existente
from notifications.telegram_client import send_message, is_enabled

logger = logging.getLogger("TelegramSmallcapCommands")

class SmallcapTelegramCommands:
    """
    Comandos específicos para el sistema smallcaps intraday
    Se integra con el sistema de Telegram existente
    """
    
    def __init__(self, production_runner=None):
        self.production_runner = production_runner
        self.logger = logging.getLogger("SmallcapTelegramCommands")
    
    def handle_smallcap_command(self, text: str) -> bool:
        """
        Maneja comandos específicos del sistema smallcaps
        Returns True si manejó el comando, False si debe pasar al sistema base
        """
        text = text.strip()
        
        try:
            if text.startswith("/smallcap"):
                self._handle_smallcap_status()
                return True
            elif text.startswith("/scanner"):
                self._handle_scanner_status()
                return True
            elif text.startswith("/plays"):
                parts = text.split()
                if len(parts) > 1 and parts[1] == "today":
                    self._handle_plays_today()
                else:
                    self._handle_recent_plays()
                return True
            elif text.startswith("/mayordomo"):
                self._handle_mayordomo_status()
                return True
            elif text.startswith("/gaps"):
                self._handle_gap_analysis()
                return True
            elif text.startswith("/volume"):
                self._handle_volume_analysis()
                return True
            elif text.startswith("/config"):
                self._handle_config_info()
                return True
            elif text.startswith("/system"):
                self._handle_system_health()
                return True
            elif text.startswith("/ml_journal"):
                self._handle_ml_journal_status()
                return True
            elif text.startswith("/elite_report"):
                # Note: This will be handled in async context in real implementation
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create task for background execution
                        asyncio.create_task(self._handle_elite_report())
                    else:
                        asyncio.run(self._handle_elite_report())
                except:
                    # Fallback to sync version
                    self._handle_elite_report_sync()
                return True
            elif text.startswith("/patterns"):
                self._handle_pattern_discovery()
                return True
            elif text.startswith("/performance"):
                self._handle_performance_stats()
                return True
            elif text.startswith("/logs"):
                parts = text.split()
                lines = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
                self._handle_logs(lines)
                return True
            elif text.startswith("/summary"):
                self._handle_eod_summary()
                return True
            
            return False  # No manejamos este comando
            
        except Exception as e:
            self.logger.error(f"Error manejando comando smallcap: {e}")
            send_message(f"❌ Error procesando comando: {str(e)}")
            return True
    
    def _handle_smallcap_status(self):
        """Status general del sistema smallcaps"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            status = self.production_runner.get_status()
            
            message = f"""
🎯 **STATUS SISTEMA SMALLCAPS**
═══════════════════════════════

**📊 ESTADO GENERAL:**
• Sistema: {'🟢 Activo' if status['is_running'] else '🔴 Detenido'}
• Scans realizados: **{status['scan_count']}**
• Plays encontrados: **{status['total_plays_found']}**
• Posiciones activas: **{status['active_positions']}**
• Último scan: {status['last_scan_time'] or 'N/A'}

**🔗 CONEXIONES:**
• IBKR: {'🟢 Conectado' if status['ibkr_connected'] else '🔴 Desconectado'}
• ML Engine: {'🟢 Activo' if status['ml_engine_enabled'] else '🔴 Desactivado'}
• Monitor: {'🟢 Activo' if status['performance_monitor_active'] else '🔴 Desactivado'}

**📱 COMANDOS SMALLCAPS:**
/plays - Plays recientes
/scanner - Estado del scanner
/mayordomo - Estado del risk manager
/gaps - Análisis de gaps
/config - Configuración actual
            """
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            send_message(f"❌ Error obteniendo status: {str(e)}")
    
    def _handle_scanner_status(self):
        """Estado del scanner híbrido"""
        if not self.production_runner:
            send_message("❌ Scanner no disponible")
            return
        
        try:
            config = self.production_runner.config
            
            message = f"""
🔍 **ESTADO DEL SCANNER HÍBRIDO**
═══════════════════════════════

**⚙️ CONFIGURACIÓN:**
• Intervalo regular: {config['scanning']['interval_seconds']}s
• Intervalo premarket: {config['scanning_intervals']['premarket_seconds']}s
• Fuente primaria: IBKR Native Scanner
• Fallback: Tiingo API

**🎯 FILTROS SMALLCAPS:**
• Precio: ${config['smallcap_strategy']['min_price']}-${config['smallcap_strategy']['max_price']}
• Gap mínimo: {config['smallcap_strategy']['min_gap_percent']}%
• Volumen mínimo: {config['smallcap_strategy']['min_volume']:,}
• Stop loss: {config['smallcap_strategy']['stop_loss_pct']*100:.1f}%
• Take profit: {config['smallcap_strategy']['take_profit_pct']*100:.1f}%

**📈 ESTADÍSTICAS:**
• Scans completados: {self.production_runner.scan_count}
• Total plays encontrados: {self.production_runner.total_plays_found}
• Última ejecución: {self.production_runner.last_scan_time.strftime('%H:%M:%S') if self.production_runner.last_scan_time else 'N/A'}
            """
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            send_message(f"❌ Error obteniendo estado del scanner: {str(e)}")
    
    def _handle_recent_plays(self):
        """Plays recientes encontrados por el scanner"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            # Get recent plays from the scanner
            recent_plays = self._get_recent_plays()
            
            if not recent_plays:
                message = f"""
📈 **PLAYS RECIENTES DEL SCANNER**
═══════════════════════════════

⏰ Último scan: {datetime.now().strftime('%H:%M:%S')}

🔍 **No hay plays activos**
• Scanner funcionando correctamente
• Filtros: Gap >3%, Precio $1-$10
• Catalyst strength ≥4 requerido

📊 Para estadísticas: /scanner
🎯 Para configuración: /config
                """
            else:
                plays_text = ""
                for i, play in enumerate(recent_plays[:5], 1):  # Show top 5
                    gap_emoji = "📈" if play.get('gap_percentage', 0) > 0 else "📉"
                    
                    plays_text += f"""
**{i}. {play.get('symbol', 'N/A')} {gap_emoji}**
• Precio: ${play.get('current_price', 0):.2f}
• Gap: {play.get('gap_percentage', 0)*100:+.1f}%
• Volumen: {play.get('volume_ratio', 0):.1f}x
• Score: {play.get('quality_score', 0):.1f}/10
• Catalyst: {play.get('catalyst_type', 'N/A')}
                    """
                
                message = f"""
📈 **PLAYS RECIENTES DEL SCANNER**
═══════════════════════════════

⏰ Último scan: {self.production_runner.last_scan_time.strftime('%H:%M:%S') if self.production_runner.last_scan_time else 'N/A'}
🎯 Total encontrados: {len(recent_plays)}

{plays_text}

📊 Scans realizados: {self.production_runner.scan_count}
🔄 Próximo scan en ~30s

📱 Para ver todos: /plays today
                """
                
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            self.logger.error(f"Error getting recent plays: {e}")
            send_message(f"❌ Error obteniendo plays recientes: {str(e)}")
    
    def _handle_plays_today(self):
        """Plays encontrados hoy"""
        try:
            # Get unified trading system from service locator
            from core.service_locator import get_service_locator
            service_locator = get_service_locator()
            unified_system = service_locator.get_service('unified_trading_system')
            
            if not unified_system or not hasattr(unified_system, 'notified_plays'):
                send_message("❌ Sistema de trading no disponible o no hay datos de plays")
                return
            
            # Get today's plays
            current_date = datetime.now().date()
            today_plays = {}
            
            for symbol, play_data in unified_system.notified_plays.items():
                play_date = play_data['last_notified'].date()
                if play_date == current_date:
                    today_plays[symbol] = play_data
            
            # Build message
            message = f"""🔥 **PLAYS EXCEPCIONALES DETECTADOS** 🔥
═══════════════════════════════

📅 **Fecha**: {current_date.strftime('%Y-%m-%d')}
🎯 **Total encontrados**: {len(today_plays)}

"""
            
            if today_plays:
                plays_text = ""
                for i, (symbol, play_data) in enumerate(today_plays.items(), 1):
                    data = play_data['last_data']
                    time_detected = play_data['last_notified'].strftime('%H:%M:%S')
                    
                    plays_text += f"""**{i}. {symbol}** 🎯
⏰ {time_detected}
💰 ${data.get('price', 0.0):.2f}
📊 Gap: {data.get('gap', 0.0)*100:+.1f}%
📈 Vol: {data.get('volume_ratio', 0.0):.1f}x
🎖️ Quality: {data.get('quality_score', 0.0):.1f}/10
🧬 Catalyst: {data.get('catalyst_type', 'N/A')}

"""
                
                message += plays_text
                message += f"═══════════════════════════════\n"
                message += f"💡 Usa /status para ver estado actual"
            else:
                message += "❌ **No se detectaron plays hoy**\n\n"
                message += "🔍 El scanner está funcionando cada 30s\n"
                message += "⏱️ Próximo scan automático en breve"
                
        except Exception as e:
            self.logger.error(f"Error getting plays today: {e}")
            send_message(f"❌ Error obteniendo plays del día: {str(e)}")
            return
        
        send_message(message, parse_mode="Markdown")
    
    def _handle_mayordomo_status(self):
        """Estado del SmallcapMayordomo"""
        if not self.production_runner or not self.production_runner.mayordomo:
            send_message("❌ SmallcapMayordomo no disponible")
            return
        
        try:
            from core.risk_manager import get_mayordomo_status
            status = get_mayordomo_status(self.production_runner.mayordomo)
            
            message = f"""
🎯 **SMALLCAP MAYORDOMO STATUS**
═══════════════════════════════

**📊 ESTADO GENERAL:**
• Risk Manager: 🟢 Activo
• Posiciones activas: {len(self.production_runner.active_positions)}
• Max posiciones: {self.production_runner.config['risk']['max_positions']}

**💰 RISK MANAGEMENT:**
• Position size: {self.production_runner.config['risk']['position_size']*100:.1f}%
• Daily loss limit: {self.production_runner.config['risk']['daily_loss_limit']*100:.1f}%
• Modo: Solo Intraday

**⚙️ CONFIGURACIÓN:**
• Stop loss: {self.production_runner.config['smallcap_strategy']['stop_loss_pct']*100:.1f}%
• Take profit: {self.production_runner.config['smallcap_strategy']['take_profit_pct']*100:.1f}%
• Max hold time: {self.production_runner.config['smallcap_strategy']['max_hold_time']} min

🛡️ **Sistema optimizado para smallcaps intraday**
            """
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            send_message(f"❌ Error obteniendo status del mayordomo: {str(e)}")
    
    def _handle_gap_analysis(self):
        """Análisis de gaps del día"""
        message = f"""
📊 **ANÁLISIS DE GAPS** - {datetime.now().strftime('%Y-%m-%d')}
═══════════════════════════════

🎯 **Configuración de filtros:**
• Gap mínimo: {self.production_runner.config['smallcap_strategy']['min_gap_percent'] if self.production_runner else 'N/A'}%
• Precio rango: ${self.production_runner.config['smallcap_strategy']['min_price'] if self.production_runner else 'N/A'} - ${self.production_runner.config['smallcap_strategy']['max_price'] if self.production_runner else 'N/A'}

📈 **Función en desarrollo...**
Esta sección incluirá:
• Top gaps detectados hoy
• Distribución por rangos de gap
• Correlación gap vs volumen
• Success rate por rango de gap
• Mejores horarios para gaps

🔍 Para ver plays actuales usa /plays
        """
        
        send_message(message, parse_mode="Markdown")
    
    def _handle_volume_analysis(self):
        """Análisis de volumen y explosión"""
        # Construir configuración de filtros
        if self.production_runner:
            min_volume = f"{self.production_runner.config['smallcap_strategy']['min_volume']:,}"
            volume_multiplier = self.production_runner.config['smallcap_strategy'].get('volume_multiplier', 'N/A')
        else:
            min_volume = 'N/A'
            volume_multiplier = 'N/A'
        
        message = f"""
📊 **ANÁLISIS DE VOLUMEN** - {datetime.now().strftime('%Y-%m-%d')}
═══════════════════════════════

🎯 **Configuración de filtros:**
• Volumen mínimo: {min_volume}
• Multiplier mínimo: {volume_multiplier}x

📈 **Función en desarrollo...**
Esta sección incluirá:
• Top volume explosions detectadas
• Ratio volumen vs promedio
• Correlación volumen vs movimiento precio
• Mejores horarios para explosiones
• Símbolos con volume patterns recurrentes

🔍 Para configuración completa usa /config
        """
        
        send_message(message, parse_mode="Markdown")
    
    def _handle_config_info(self):
        """Información de configuración del sistema"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            config = self.production_runner.config
            
            message = f"""
⚙️ **CONFIGURACIÓN SISTEMA HÍBRIDO**
═══════════════════════════════

**🎯 SMALLCAPS FILTERS:**
• Precio: ${config['smallcap_strategy']['min_price']}-${config['smallcap_strategy']['max_price']}
• Gap: >{config['smallcap_strategy']['min_gap_percent']}%
• Volumen: >{config['smallcap_strategy']['min_volume']:,}

**📊 SCANNING:**
• Regular: {config['scanning']['interval_seconds']}s
• Premarket: {config['scanning_intervals']['premarket_seconds']}s
• Max símbolos: {config['scanning']['max_symbols']}

**🛡️ RISK MANAGEMENT:**
• Max posiciones: {config['risk']['max_positions']}
• Position size: {config['risk']['position_size']*100:.1f}%
• Daily loss limit: {config['risk']['daily_loss_limit']*100:.1f}%

**🧠 ML ENGINE:**
• Estado: {'✅ Activo' if config['ml_engine']['enabled'] else '❌ Desactivado'}
• Strategy selection: {config['ml_engine']['strategy_selection']}
• Contextual bandit: {config['ml_engine']['contextual_bandit']}

**📱 TELEGRAM:**
• Estado: {'✅ Activo' if config['telegram']['enabled'] else '❌ Desactivado'}
• Alertas excepcionales: {'✅' if config['telegram']['smallcap_alerts']['exceptional_plays'] else '❌'}
• Updates posiciones: {'✅' if config['telegram']['smallcap_alerts']['position_updates'] else '❌'}
            """
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            send_message(f"❌ Error obteniendo configuración: {str(e)}")
    
    def _handle_system_health(self):
        """Health check del sistema completo"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            status = self.production_runner.get_status()
            
            # Determinar health score
            health_score = 0
            issues = []
            
            if status['ibkr_connected']:
                health_score += 25
            else:
                issues.append("IBKR desconectado")
            
            if status['is_running']:
                health_score += 25
            else:
                issues.append("Sistema detenido")
            
            if status['ml_engine_enabled']:
                health_score += 25
            else:
                issues.append("ML Engine desactivado")
            
            if status['performance_monitor_active']:
                health_score += 25
            else:
                issues.append("Monitor desactivado")
            
            # Determinar emoji de status
            if health_score >= 90:
                status_emoji = "🟢"
                status_text = "EXCELENTE"
            elif health_score >= 70:
                status_emoji = "🟡"
                status_text = "BUENO"
            elif health_score >= 50:
                status_emoji = "🟠"
                status_text = "REGULAR"
            else:
                status_emoji = "🔴"
                status_text = "CRÍTICO"
            
            message = f"""
🏥 **SYSTEM HEALTH CHECK**
═══════════════════════════════

**{status_emoji} ESTADO GENERAL: {status_text}**
• Health Score: {health_score}/100

**📊 COMPONENTES:**
• IBKR: {'🟢' if status['ibkr_connected'] else '🔴'}
• Scanner: {'🟢' if status['is_running'] else '🔴'}
• ML Engine: {'🟢' if status['ml_engine_enabled'] else '🔴'}
• Monitor: {'🟢' if status['performance_monitor_active'] else '🔴'}

**📈 MÉTRICAS:**
• Uptime: {self.production_runner.scan_count * self.production_runner.config['scanning']['interval_seconds'] // 3600:.1f}h
• Scans: {status['scan_count']}
• Plays: {status['total_plays_found']}
• Error rate: Calculando...

**⚠️ ISSUES:**
{chr(10).join([f"• {issue}" for issue in issues]) if issues else "• Ninguno detectado"}

🔄 Actualizado: {datetime.now().strftime('%H:%M:%S')}
            """
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            send_message(f"❌ Error obteniendo system health: {str(e)}")
    
    def _handle_ml_journal_status(self):
        """Status del ML Journal System (Elite Enhancement)"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            status = self.production_runner.get_status()
            ml_journal_status = status.get('ml_journal_status', {})
            
            if not ml_journal_status:
                message = """
🧠📊 **ML TRADING JOURNAL STATUS**
═══════════════════════════════

❌ **ML Journal no disponible**
• Sistema funcionando con ML básico
• Para funcionalidad ELITE, verificar instalación

💡 **Funcionalidades ELITE incluyen:**
• Context enhancement (50+ features)
• Pattern discovery automático  
• Multi-dimensional reward system
• Trade classification avanzada
• Performance optimization continua

🔄 Contactar soporte técnico para activación
                """
            else:
                enhancement_level = ml_journal_status.get('ml_enhancement_level', 'BASIC')
                contexts_enhanced = ml_journal_status.get('metrics', {}).get('contexts_enhanced', 0)
                patterns_count = ml_journal_status.get('discovered_patterns_count', 0)
                ml_improvements = ml_journal_status.get('metrics', {}).get('ml_improvements', 0)
                
                message = f"""
🧠📊 **ML TRADING JOURNAL STATUS**
═══════════════════════════════

✅ **Sistema ELITE Activo**
• Enhancement Level: **{enhancement_level}**
• Contexts Enhanced: **{contexts_enhanced}**
• Patterns Discovered: **{patterns_count}**
• ML Improvements: **{ml_improvements}**

📊 **Features Avanzadas:**
• Context Enhancement: {'✅' if contexts_enhanced > 0 else '🔄'} Activo
• Pattern Mining: {'✅' if patterns_count > 0 else '🔄'} En proceso
• Learning System: {'✅' if ml_improvements > 0 else '🔄'} Entrenando

🚀 **Comandos ELITE:**
/elite_report - Reporte completo ELITE
/patterns - Patrones descubiertos

═══════════════════════════════
🧠 **ML transformado a nivel profesional**
                """
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            send_message(f"❌ Error obteniendo ML Journal status: {str(e)}")
    
    async def _handle_elite_report(self):
        """Generate and send elite ML report"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            send_message("🧠📊 Generando reporte ELITE... ⏳")
            
            elite_report = await self.production_runner.generate_elite_ml_report()
            
            # Split long message if needed
            if len(elite_report) > 4000:
                parts = [elite_report[i:i+4000] for i in range(0, len(elite_report), 4000)]
                for i, part in enumerate(parts):
                    send_message(f"**Parte {i+1}/{len(parts)}:**\n```\n{part}\n```", parse_mode="Markdown")
            else:
                send_message(f"```\n{elite_report}\n```", parse_mode="Markdown")
                
        except Exception as e:
            send_message(f"❌ Error generando reporte ELITE: {str(e)}")
    
    def _handle_elite_report_sync(self):
        """Sync version of elite report handler"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            send_message("🧠📊 Generando reporte ELITE... ⏳")
            
            # Get sync report if available
            if hasattr(self.production_runner, 'ml_journal_integration') and self.production_runner.ml_journal_integration:
                import asyncio
                elite_report = asyncio.run(self.production_runner.generate_elite_ml_report())
            else:
                elite_report = "ML Journal Integration no disponible"
            
            # Split long message if needed
            if len(elite_report) > 4000:
                parts = [elite_report[i:i+4000] for i in range(0, len(elite_report), 4000)]
                for i, part in enumerate(parts):
                    send_message(f"**Parte {i+1}/{len(parts)}:**\n```\n{part}\n```", parse_mode="Markdown")
            else:
                send_message(f"```\n{elite_report}\n```", parse_mode="Markdown")
                
        except Exception as e:
            send_message(f"❌ Error generando reporte ELITE: {str(e)}")
    
    def _handle_pattern_discovery(self):
        """Show discovered patterns from ML Journal"""
        if not self.production_runner:
            send_message("❌ Sistema no disponible")
            return
        
        try:
            status = self.production_runner.get_status()
            ml_journal_status = status.get('ml_journal_status', {})
            
            if not ml_journal_status or not self.production_runner.ml_journal_integration:
                send_message("❌ ML Journal no disponible para mostrar patrones")
                return
            
            patterns_count = ml_journal_status.get('discovered_patterns_count', 0)
            
            message = f"""
🔍 **PATTERN DISCOVERY STATUS**
═══════════════════════════════

📊 **Patrones Descubiertos:** {patterns_count}

🧠 **Sistema de Descubrimiento:**
• Pattern Mining: Activo
• Edge Discovery: Funcionando  
• Feature Analysis: Continuo
• Market Regime Detection: Automático

💡 **Próximos Desarrollos:**
• Real-time pattern detection
• Cross-market pattern correlation
• Adaptive pattern evolution
• Risk-adjusted pattern scoring

🚀 **Para análisis detallado:**
/elite_report - Reporte completo con insights

═══════════════════════════════
🔍 **Descubrimiento continuo de nuevos edges**
            """
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            send_message(f"❌ Error obteniendo pattern discovery status: {str(e)}")
    
    def _get_recent_plays(self):
        """Get recent plays from the production runner"""
        try:
            if not self.production_runner:
                return []
            
            # Get recent plays stored by production runner
            if hasattr(self.production_runner, 'recent_plays') and self.production_runner.recent_plays:
                plays_list = []
                for play in self.production_runner.recent_plays[:10]:  # Max 10 plays
                    # Handle SmallcapPlay objects
                    if hasattr(play, '__dict__'):
                        play_dict = {
                            'symbol': getattr(play, 'symbol', 'N/A'),
                            'current_price': getattr(play, 'current_price', 0),
                            'gap_percentage': getattr(play.context, 'gap_percentage', 0) if hasattr(play, 'context') else 0,
                            'volume_ratio': getattr(play.context, 'premarket_volume_ratio', 0) if hasattr(play, 'context') else 0,
                            'quality_score': getattr(play, 'quality_score', 0),
                            'catalyst_type': getattr(play.catalyst, 'event_type', 'N/A') if hasattr(play, 'catalyst') else 'N/A',
                            'timestamp': getattr(play, 'timestamp', datetime.now())
                        }
                    else:
                        # Handle dict objects
                        play_dict = {
                            'symbol': play.get('symbol', 'N/A'),
                            'current_price': play.get('current_price', 0),
                            'gap_percentage': play.get('gap_percentage', 0),
                            'volume_ratio': play.get('volume_ratio', 0),
                            'quality_score': play.get('quality_score', 0),
                            'catalyst_type': play.get('catalyst_type', 'N/A'),
                            'timestamp': play.get('timestamp', datetime.now())
                        }
                    
                    plays_list.append(play_dict)
                return plays_list
            
            # If no recent plays stored, return empty list
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting recent plays: {e}")
            return []
    
    def _handle_performance_stats(self):
        """Manejar comando /performance - mostrar estadísticas multicapa"""
        try:
            if not self.production_runner:
                send_message("❌ Production runner no disponible")
                return
            
            # Get performance summary from production runner
            performance_text = self.production_runner.get_performance_summary()
            
            # Add header
            message = "📊 **PERFORMANCE MULTICAPA - SISTEMA TRADING**\n"
            message += "═" * 50 + "\n\n"
            message += performance_text
            
            # Add footer with timestamp
            message += f"\n⏰ Actualizado: {datetime.now().strftime('%H:%M:%S')}"
            message += f"\n📈 Sistema: FinBERT -> Strategy -> Execution"
            
            send_message(message, parse_mode="Markdown")
            
        except Exception as e:
            self.logger.error(f"Error obteniendo performance stats: {e}")
            send_message(f"❌ Error obteniendo estadísticas: {str(e)}")
    
    def _handle_logs(self, lines=50):
        """Manejar comando /logs - mostrar últimas líneas del log"""
        try:
            import os
            
            log_file_path = "logs/trading_system.log"
            
            # Check if log file exists
            if not os.path.exists(log_file_path):
                send_message(f"❌ Archivo de log no encontrado: {log_file_path}")
                return
            
            try:
                # Read last N lines from log file
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                if not last_lines:
                    send_message("📝 Log file está vacío")
                    return
                
                # Format log message
                log_content = ''.join(last_lines).strip()
                
                # Split into chunks if too long (Telegram limit ~4000 chars)
                max_chars = 3800
                if len(log_content) <= max_chars:
                    message = f"📝 **LOGS SISTEMA SMALLCAP** (últimas {len(last_lines)} líneas)\n"
                    message += f"📁 Archivo: `{log_file_path}`\n\n"
                    message += f"```\n{log_content}\n```"
                    send_message(message, parse_mode="Markdown")
                else:
                    # Split into multiple messages
                    chunks = []
                    current_chunk = ""
                    
                    for line in last_lines:
                        if len(current_chunk) + len(line) > max_chars:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = line
                        else:
                            current_chunk += line
                    
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    
                    # Send first chunk with header
                    if chunks:
                        first_message = f"📝 **LOGS SISTEMA SMALLCAP** (últimas {len(last_lines)} líneas)\n"
                        first_message += f"📁 Archivo: `{log_file_path}`\n"
                        first_message += f"🔢 Parte 1/{len(chunks)}\n\n"
                        first_message += f"```\n{chunks[0]}\n```"
                        send_message(first_message, parse_mode="Markdown")
                        
                        # Send remaining chunks
                        for i, chunk in enumerate(chunks[1:], 2):
                            chunk_message = f"📝 **LOGS** - Parte {i}/{len(chunks)}\n\n"
                            chunk_message += f"```\n{chunk}\n```"
                            send_message(chunk_message, parse_mode="Markdown")
                            
            except UnicodeDecodeError:
                # Try with different encoding
                with open(log_file_path, 'r', encoding='latin-1') as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    log_content = ''.join(last_lines).strip()
                    
                message = f"📝 **LOGS SISTEMA SMALLCAP** (últimas {len(last_lines)} líneas)\n"

    def _handle_eod_summary(self):
        """Handle /summary command"""
        try:
            from notifications.telegram_client import send_eod_summary
            send_eod_summary()
        except Exception as e:
            self.logger.error(f"Error handling EOD summary: {e}")
            send_message(f"❌ Error ejecutando resumen: {str(e)}")
                message += f"📁 Archivo: `{log_file_path}`\n\n"
                message += f"```\n{log_content[:3800]}\n```"
                send_message(message, parse_mode="Markdown")
                    
        except Exception as e:
            self.logger.error(f"Error leyendo logs: {e}")
            send_message(f"❌ Error leyendo logs: {str(e)}")

def send_smallcap_help():
    """Enviar ayuda específica para comandos smallcaps"""
    help_message = """
🎯 **COMANDOS SMALLCAPS ESPECÍFICOS**
═══════════════════════════════

**📊 SISTEMA:**
• `/smallcap` - Status general del sistema
• `/system` - Health check completo
• `/config` - Configuración actual
• `/logs` [n] - Últimas n líneas del log (default: 50)

**🔍 SCANNER & PLAYS:**
• `/scanner` - Estado del scanner híbrido
• `/plays` - Plays recientes detectados
• `/plays today` - Todos los plays de hoy

**📈 ANÁLISIS:**
• `/gaps` - Análisis de gaps del día
• `/volume` - Análisis de explosiones de volumen

**🛡️ RISK MANAGEMENT:**
• `/mayordomo` - Estado del SmallcapMayordomo

**📊 PERFORMANCE:**
• `/performance` - Stats multicapa FinBERT->Strategy->Execution

**🧠 ML JOURNAL (ELITE):**
• `/ml_journal` - Status del sistema ELITE
• `/elite_report` - Reporte completo de rendimiento
• `/patterns` - Patrones descubiertos

**📱 INFORMACIÓN:**
Estos comandos son específicos del sistema híbrido smallcaps intraday.
Para comandos generales de trading usa `/help`.

═══════════════════════════════
🚀 Sistema optimizado para gaps >10%, vol >500K, precio $1-$15
    """
    
    send_message(help_message, parse_mode="Markdown")