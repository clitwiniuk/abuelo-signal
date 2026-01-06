#!/usr/bin/env python3
"""
Scanner Intelligence System - Updated to use existing DatabaseManager
Sistema de aprendizaje continuo para scanner integrado con base de datos existente
"""

import sqlite3
import json
import re
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class SentimentType(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral" 
    NEGATIVE = "negative"

class CatalystType(Enum):
    EARNINGS = "earnings"
    FDA = "fda"
    MERGER = "merger"
    PARTNERSHIP = "partnership"
    CONTRACT = "contract"
    BREAKTHROUGH = "breakthrough"
    CRYPTO = "crypto"
    OIL_GAS = "oil_gas"
    CLINICAL = "clinical"
    ACQUISITION = "acquisition"
    INNOVATION = "innovation"
    OTHER = "other"

@dataclass
class NewsAnalysis:
    ticker: str
    date: date
    sentiment: SentimentType
    catalyst_type: CatalystType
    confidence_score: float  # 0-1
    impact_score: float      # 0-1  
    keywords: List[str]
    source_text: str

@dataclass
class TradingResult:
    ticker: str
    trade_date: date
    entry_price: float
    exit_price: Optional[float]
    pnl: Optional[float]
    was_profitable: bool
    hold_duration_minutes: Optional[int]
    strategy_used: str
    notes: str

@dataclass 
class AdvancedTradingResult:
    """Advanced trading result with comprehensive analysis"""
    ticker: str
    trade_date: date
    pnl: Optional[float]
    
    # Advanced categorization fields
    trade_category: str  # "Gap Play", "News Catalyst", "Breakout", etc.
    context_type: str    # "Pre-market", "Open", "Mid-day", etc.
    market_context: str  # "Bull Market", "Bear Market", "Sideways", etc.
    why_in_play: str
    daily_volume_context: str
    intraday_volume_context: str
    daily_chart_analysis: str
    intraday_chart_analysis: str
    how_you_traded: str
    followed_system: bool
    sizing_appropriate: bool
    execution_quality: str  # "Excellent", "Good", "Fair", "Poor"
    how_should_have_traded: str
    key_takeaways: str
    changes_to_make: str
    
    # Technical fields
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    hold_duration_minutes: Optional[int] = None
    strategy_used: Optional[str] = None

class AutoCategorizer:
    """Intelligent auto-categorization system for trades"""
    
    def __init__(self):
        self.logger = logging.getLogger("AutoCategorizer")
    
    def categorize_trade_automatically(self, ticker: str, entry_price: float, 
                                     exit_price: Optional[float], trade_date: date,
                                     hold_duration_minutes: Optional[int],
                                     strategy_used: str, pnl: Optional[float]) -> AdvancedTradingResult:
        """Auto-categorize a trade based on available data"""
        
        try:
            # Calculate basic metrics
            if exit_price and entry_price > 0:
                price_change_pct = ((exit_price - entry_price) / entry_price) * 100
                gap_percent = 0.0  # Could be enhanced with pre-market data
            else:
                price_change_pct = 0.0
                gap_percent = 0.0
            
            # Mock volume analysis (could be enhanced with real data)
            volume_context = "Average" if abs(price_change_pct) < 5 else "High"
            
            # Mock news analysis (could be enhanced with news API)
            news_context = "No significant news" if abs(price_change_pct) < 3 else "Potential catalyst"
            
            # Determine market context based on time
            market_context = self._determine_market_context(trade_date)
            
            # Determine trade category
            trade_category = self._determine_trade_category(
                gap_percent, volume_context, news_context, strategy_used, entry_price, exit_price
            )
            
            # Determine context type
            context_type = self._determine_context_type(news_context, gap_percent, volume_context)
            
            # Analyze execution quality
            execution_quality = self._analyze_execution_quality(
                entry_price, exit_price, hold_duration_minutes, pnl
            )
            
            # Create advanced result
            return AdvancedTradingResult(
                ticker=ticker,
                trade_date=trade_date,
                pnl=pnl,
                trade_category=trade_category,
                context_type=context_type,
                market_context=market_context,
                why_in_play=f"Auto-detected: {self._generate_why_in_play(trade_category, gap_percent, volume_context)}",
                daily_volume_context=volume_context,
                intraday_volume_context=volume_context,  # Same for now
                daily_chart_analysis=f"Auto: Gap {gap_percent:.1f}%, Volume {volume_context}",
                intraday_chart_analysis=f"Auto: {trade_category} setup detected",
                how_you_traded=f"Executed via {strategy_used} strategy",
                followed_system=True,  # System trades always follow system
                sizing_appropriate=True,  # Assume system sizing is appropriate
                execution_quality=execution_quality,
                how_should_have_traded="System-executed trade",
                key_takeaways=f"Auto-categorized {trade_category} with {execution_quality} execution",
                changes_to_make="Review via manual journal if needed",
                entry_price=entry_price,
                exit_price=exit_price,
                hold_duration_minutes=hold_duration_minutes,
                strategy_used=strategy_used
            )
            
        except Exception as e:
            self.logger.error(f"Error in auto-categorization: {e}")
            # Return basic result if auto-categorization fails
            return AdvancedTradingResult(
                ticker=ticker,
                trade_date=trade_date,
                pnl=pnl,
                trade_category="Unknown",
                context_type="Unknown",
                market_context="Unknown",
                why_in_play="Auto-categorization failed",
                daily_volume_context="Unknown",
                intraday_volume_context="Unknown",
                daily_chart_analysis="Analysis failed",
                intraday_chart_analysis="Analysis failed",
                how_you_traded="Unknown",
                followed_system=True,
                sizing_appropriate=True,
                execution_quality="Unknown",
                how_should_have_traded="Unknown",
                key_takeaways="Auto-categorization failed - manual review needed",
                changes_to_make="Manual categorization required",
                entry_price=entry_price,
                exit_price=exit_price,
                hold_duration_minutes=hold_duration_minutes,
                strategy_used=strategy_used
            )
    
    def _determine_market_context(self, trade_date: date) -> str:
        """Determine market context based on time and date"""
        now = datetime.now()
        hour = now.hour
        
        if hour < 9:
            return "Pre-market Session"
        elif hour < 12:
            return "Morning Session"
        elif hour < 15:
            return "Afternoon Session" 
        else:
            return "Late Session"
    
    def _determine_trade_category(self, gap_percent: float, volume_context: str, 
                                 news_context: str, strategy_used: str,
                                 entry_price: float, exit_price: Optional[float]) -> str:
        """Determine trade category based on setup characteristics"""
        
        if "gap" in strategy_used.lower():
            return "Gap Play"
        elif "news" in news_context.lower() or "catalyst" in news_context.lower():
            return "News Catalyst"
        elif "volume" in strategy_used.lower():
            return "Volume Breakout"
        elif "breakout" in strategy_used.lower():
            return "Technical Breakout"
        elif "macdv" in strategy_used.lower():
            return "MACD Volume"
        else:
            return "Strategy Play"
    
    def _determine_context_type(self, news_context: str, gap_percent: float, volume_context: str) -> str:
        """Determine the context type of the trade"""
        
        if "catalyst" in news_context.lower():
            return "News Driven"
        elif gap_percent > 5:
            return "Gap Movement"
        elif volume_context == "High":
            return "Volume Spike"
        else:
            return "Technical Setup"
    
    def _analyze_execution_quality(self, entry_price: float, exit_price: Optional[float], 
                                 hold_duration_minutes: Optional[int], pnl: Optional[float]) -> str:
        """Analyze the quality of trade execution"""
        
        if not exit_price or not pnl:
            return "Incomplete"
        
        # Analyze based on PnL and hold time
        if pnl > 0:
            if hold_duration_minutes and hold_duration_minutes < 30:
                return "Excellent"  # Quick profitable exit
            elif hold_duration_minutes and hold_duration_minutes < 120:
                return "Good"      # Reasonable hold time with profit
            else:
                return "Fair"      # Long hold but profitable
        else:
            if hold_duration_minutes and hold_duration_minutes < 60:
                return "Good"      # Quick cut of losses
            else:
                return "Poor"      # Held losers too long
    
    
    def _generate_why_in_play(self, trade_category: str, gap_percent: float, volume_context: str) -> str:
        """Generate why the stock was in play"""
        
        reasons = []
        if gap_percent > 5:
            reasons.append(f"{gap_percent:.1f}% gap")
        if volume_context == "High":
            reasons.append("elevated volume")
        if trade_category == "News Catalyst":
            reasons.append("news catalyst")
        
        return ", ".join(reasons) if reasons else "technical setup"

@dataclass
class ScannerConfig:
    """Configuración del scanner inteligente"""
    min_volume: int
    auto_add_threshold: float  # ML score threshold for auto-add
    learning_enabled: bool
    sentiment_filter: str = "POSITIVE_NEUTRAL"  # "ONLY_POSITIVE", "POSITIVE_NEUTRAL", "ALL"
    max_float: float = 10_000_000.0  # Maximum float value for volume slider

class ScannerIntelligence:
    """Sistema inteligente de scanner integrado con DatabaseManager existente"""
    
    def __init__(self, database_manager=None):
        self.logger = logging.getLogger("ScannerIntelligence")
        
        # Use existing DatabaseManager instead of creating new DB
        if database_manager:
            self.db_manager = database_manager
        else:
            from core.database_manager import get_database_manager
            self.db_manager = get_database_manager()
            
        self.auto_categorizer = AutoCategorizer()
        self._setup_advanced_tables()  # Setup additional tables if needed
        
        self.catalyst_keywords = {
            CatalystType.EARNINGS: ["earnings", "beat", "eps", "revenue", "guidance", "quarter"],
            CatalystType.FDA: ["fda", "approval", "drug", "clinical", "trial", "phase"],
            CatalystType.MERGER: ["merger", "acquire", "buyout", "takeover", "deal"],
            CatalystType.PARTNERSHIP: ["partnership", "collaboration", "alliance", "joint"],
            CatalystType.CONTRACT: ["contract", "deal", "agreement", "award"],
            CatalystType.BREAKTHROUGH: ["breakthrough", "innovation", "discovery"],
            CatalystType.CRYPTO: ["bitcoin", "crypto", "blockchain", "nft"],
            CatalystType.OIL_GAS: ["oil", "gas", "energy", "pipeline"],
            CatalystType.CLINICAL: ["phase", "trial", "patient", "study"],
            CatalystType.ACQUISITION: ["acquisition", "acquire", "purchase"],
            CatalystType.INNOVATION: ["patent", "technology", "ai", "software"]
        }
        
        self.sentiment_keywords = {
            "positive": [
                "beat", "exceed", "strong", "growth", "bullish", "upgrade", "buy",
                "outperform", "positive", "good", "great", "excellent", "success",
                "win", "gain", "increase", "rise", "surge", "breakthrough"
            ],
            "negative": [
                "miss", "decline", "weak", "bearish", "downgrade", "rejection",
                "fail", "loss", "drop", "negative", "underperform", "cut",
                "warning", "concern", "disappoint"
            ]
        }
        
    def _setup_advanced_tables(self):
        """Setup additional tables for advanced journal functionality"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # Create advanced_trading_results table for auto-categorized data
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS advanced_trading_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT,
                        ticker TEXT NOT NULL,
                        trade_date DATE NOT NULL,
                        pnl REAL,
                        trade_category TEXT,
                        context_type TEXT,
                        market_context TEXT,
                        why_in_play TEXT,
                        daily_volume_context TEXT,
                        intraday_volume_context TEXT,
                        daily_chart_analysis TEXT,
                        intraday_chart_analysis TEXT,
                        how_you_traded TEXT,
                        followed_system BOOLEAN,
                        sizing_appropriate BOOLEAN,
                        execution_quality TEXT,
                        how_should_have_traded TEXT,
                        key_takeaways TEXT,
                        changes_to_make TEXT,
                        entry_price REAL,
                        exit_price REAL,
                        hold_duration_minutes INTEGER,
                        strategy_used TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
                    )
                """)
                conn.commit()
                self.logger.info("Advanced trading results table setup completed")
        except Exception as e:
            self.logger.error(f"Error setting up advanced tables: {e}")
    
    def add_trading_result(self, result: TradingResult, trade_id: str = None):
        """Añadir resultado de trading usando DatabaseManager existente"""
        
        try:
            # First save to main trades table using existing DatabaseManager
            trade_data = {
                'trade_id': trade_id or f"{result.ticker}_{result.trade_date.isoformat()}_{result.entry_price}",
                'symbol': result.ticker,
                'strategy': result.strategy_used,
                'side': 'BUY',  # Assuming long positions for now
                'quantity': 100,  # Default quantity - could be passed as parameter
                'entry_price': result.entry_price,
                'exit_price': result.exit_price,
                'entry_time': result.trade_date.strftime('%Y-%m-%d %H:%M:%S'),
                'exit_time': result.trade_date.strftime('%Y-%m-%d %H:%M:%S') if result.exit_price else None,
                'duration_minutes': result.hold_duration_minutes,
                'pnl': result.pnl,
                'status': 'CLOSED' if result.exit_price else 'OPEN',
                'notes': result.notes
            }
            
            # Save using existing DatabaseManager
            self.db_manager.save_trade(trade_data)
        
            # 🤖 AUTO-CATEGORIZATION: Generate advanced analysis automatically
            if result.exit_price is not None and result.pnl is not None:
                try:
                    advanced_result = self.auto_categorizer.categorize_trade_automatically(
                        ticker=result.ticker,
                        entry_price=result.entry_price,
                        exit_price=result.exit_price,
                        trade_date=result.trade_date,
                        hold_duration_minutes=result.hold_duration_minutes,
                        strategy_used=result.strategy_used,
                        pnl=result.pnl
                    )
                    
                    # Store advanced categorization using new table
                    self._store_advanced_trading_result(advanced_result, trade_data['trade_id'])
                    
                    self.logger.info(f"🤖 Auto-categorized {result.ticker} as {advanced_result.trade_category} ({advanced_result.execution_quality} execution)")
                    
                except Exception as e:
                    self.logger.error(f"Error in auto-categorization for {result.ticker}: {e}")
            
            self.logger.info(f"Trading result added for {result.ticker}")
            
        except Exception as e:
            self.logger.error(f"Error adding trading result for {result.ticker}: {e}")
    
    def _store_advanced_trading_result(self, advanced_result: AdvancedTradingResult, trade_id: str):
        """Store advanced trading result in database"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("""
                    INSERT INTO advanced_trading_results (
                        trade_id, ticker, trade_date, pnl, trade_category, context_type,
                        market_context, why_in_play, daily_volume_context, intraday_volume_context,
                        daily_chart_analysis, intraday_chart_analysis, how_you_traded, followed_system,
                        sizing_appropriate, execution_quality, how_should_have_traded,
                        key_takeaways, changes_to_make, entry_price, exit_price, hold_duration_minutes,
                        strategy_used
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id, advanced_result.ticker, advanced_result.trade_date, advanced_result.pnl,
                    advanced_result.trade_category, advanced_result.context_type, advanced_result.market_context,
                    advanced_result.why_in_play, advanced_result.daily_volume_context, advanced_result.intraday_volume_context,
                    advanced_result.daily_chart_analysis, advanced_result.intraday_chart_analysis, advanced_result.how_you_traded,
                    advanced_result.followed_system, advanced_result.sizing_appropriate,
                    advanced_result.execution_quality, advanced_result.how_should_have_traded, advanced_result.key_takeaways,
                    advanced_result.changes_to_make, advanced_result.entry_price, advanced_result.exit_price,
                    advanced_result.hold_duration_minutes, advanced_result.strategy_used
                ))
                conn.commit()
                self.logger.info(f"Advanced result stored for {advanced_result.ticker}")
        except Exception as e:
            self.logger.error(f"Error storing advanced trading result: {e}")
    
    def get_advanced_trading_results(self, limit: int = 50) -> List[AdvancedTradingResult]:
        """Get advanced trading results from database"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT * FROM advanced_trading_results 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,)).fetchall()
                
                results = []
                for row in rows:
                    result = AdvancedTradingResult(
                        ticker=row['ticker'],
                        trade_date=datetime.strptime(row['trade_date'], '%Y-%m-%d').date(),
                        pnl=row['pnl'],
                        trade_category=row['trade_category'],
                        context_type=row['context_type'],
                        market_context=row['market_context'],
                        why_in_play=row['why_in_play'],
                        daily_volume_context=row['daily_volume_context'],
                        intraday_volume_context=row['intraday_volume_context'],
                        daily_chart_analysis=row['daily_chart_analysis'],
                        intraday_chart_analysis=row['intraday_chart_analysis'],
                        how_you_traded=row['how_you_traded'],
                        followed_system=row['followed_system'],
                        sizing_appropriate=row['sizing_appropriate'],
                        execution_quality=row['execution_quality'],
                        how_should_have_traded=row['how_should_have_traded'],
                        key_takeaways=row['key_takeaways'],
                        changes_to_make=row['changes_to_make'],
                        entry_price=row['entry_price'],
                        exit_price=row['exit_price'],
                        hold_duration_minutes=row['hold_duration_minutes'],
                        strategy_used=row['strategy_used']
                    )
                    results.append(result)
                
                return results
                
        except Exception as e:
            self.logger.error(f"Error getting advanced trading results: {e}")
            return []
    
    def get_learning_stats(self) -> Dict:
        """Obtener estadísticas de aprendizaje usando DatabaseManager"""
        try:
            # Get basic stats from DatabaseManager
            today_stats = self.db_manager.get_today_stats()
            
            # Get advanced results count
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # Count advanced trading results (auto-categorized trades)
                advanced_count = conn.execute("SELECT COUNT(*) FROM advanced_trading_results").fetchone()[0]
                
                # Count total trades from main table
                total_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
                
                # Calculate win rate from main trades table
                if total_trades > 0:
                    winning_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0").fetchone()[0]
                    win_rate = (winning_trades / total_trades) * 100
                else:
                    win_rate = 0.0
                
                # News analysis count (mock for now, could be enhanced)
                news_analyzed = advanced_count  # Each advanced result represents analyzed trade
            
            stats = {
                'total_news_analyzed': news_analyzed,
                'total_trades': total_trades,
                'advanced_results': advanced_count,
                'win_rate': win_rate,
                'today_trades': today_stats['total_trades'],
                'today_pnl': today_stats['total_pnl'],
                'learning_enabled': True,
                'auto_categorization_rate': (advanced_count / total_trades * 100) if total_trades > 0 else 0.0,
                'best_patterns': []  # Mock data for now, could be enhanced with pattern analysis
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting learning stats: {e}")
            return {
                'total_news_analyzed': 0,
                'total_trades': 0,
                'advanced_results': 0,
                'win_rate': 0.0,
                'today_trades': 0,
                'today_pnl': 0.0,
                'learning_enabled': False,
                'auto_categorization_rate': 0.0,
                'best_patterns': []
            }
    
    def load_config(self) -> Optional['ScannerConfig']:
        """Cargar configuración del scanner desde config.ini centralizado"""
        try:
            import configparser
            import os
            
            config_file = os.path.join(os.path.dirname(__file__), '..', 'config.ini')
            config_parser = configparser.ConfigParser()
            
            if os.path.exists(config_file):
                config_parser.read(config_file)
                
                # Load from GLOBAL and TRADING sections
                min_volume = config_parser.getint('GLOBAL', 'min_volume', fallback=1000000)
                max_float = max(min_volume * 10.0, 1_000_000.0)  # Min 1M, or 10x min_volume
                
                # Load from MULTI_STRATEGY section if exists
                learning_enabled = config_parser.getboolean('MULTI_STRATEGY', 'learning_enabled', fallback=True)
                auto_add_threshold = config_parser.getfloat('MULTI_STRATEGY', 'default_confidence_threshold', fallback=0.7)
                
                scanner_config = ScannerConfig(
                    min_volume=min_volume,
                    auto_add_threshold=auto_add_threshold,
                    learning_enabled=learning_enabled,
                    sentiment_filter="POSITIVE_NEUTRAL",  # Default for now
                    max_float=float(max_float)
                )
                
                self.logger.debug(f"Loaded scanner config from {config_file}: min_volume={min_volume}, threshold={auto_add_threshold}")
                return scanner_config
            else:
                self.logger.warning(f"Config file not found: {config_file}")
                
        except Exception as e:
            self.logger.error(f"Error loading scanner config from file: {e}")
            
        # Return default config on error or missing file
        return ScannerConfig(
            min_volume=1000000,
            auto_add_threshold=0.7,
            learning_enabled=True,
            sentiment_filter="POSITIVE_NEUTRAL",
            max_float=10_000_000.0
        )
    
    def save_config(self, config: 'ScannerConfig') -> bool:
        """Guardar configuración del scanner"""
        try:
            # For now, just log the configuration
            # In future versions, this could save to a config table
            self.logger.info(f"Scanner config updated: min_volume={config.min_volume}, "
                           f"auto_add_threshold={config.auto_add_threshold}, "
                           f"learning_enabled={config.learning_enabled}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving scanner config: {e}")
            return False
    
    def analyze_ticker_news(self, ticker: str, news_text: str = "") -> Optional[NewsAnalysis]:
        """Analizar noticias para un ticker usando sentiment_analyzer existente"""
        try:
            # Usar el sentiment analyzer existente
            from .sentiment_analyzer import CatalystSentimentAnalyzer, SentimentType as SentType
            
            analyzer = CatalystSentimentAnalyzer()
            
            if not news_text:
                news_text = f"Market analysis for {ticker}"
            
            # Análisis de sentimiento usando sistema existente
            sentiment_result = analyzer.analyze_text(news_text, ticker)
            
            # Mapear SentimentType existente a nuestro enum
            sentiment_map = {
                SentType.POSITIVE: SentimentType.POSITIVE,
                SentType.NEGATIVE: SentimentType.NEGATIVE,
                SentType.NEUTRAL: SentimentType.NEUTRAL,
                SentType.MIXED: SentimentType.NEUTRAL  # Map mixed to neutral
            }
            
            sentiment = sentiment_map.get(sentiment_result.sentiment, SentimentType.NEUTRAL)
            
            # Determinar tipo de catalizador basado en keywords
            catalyst_type = CatalystType.OTHER
            for keyword in sentiment_result.positive_keywords + sentiment_result.negative_keywords:
                if any(fda_word in keyword.lower() for fda_word in ['fda', 'approval', 'clinical']):
                    catalyst_type = CatalystType.FDA
                    break
                elif any(earn_word in keyword.lower() for earn_word in ['earnings', 'revenue', 'beat']):
                    catalyst_type = CatalystType.EARNINGS
                    break
                elif any(merge_word in keyword.lower() for merge_word in ['merger', 'acquisition', 'buyout']):
                    catalyst_type = CatalystType.MERGER
                    break
                elif any(partner_word in keyword.lower() for partner_word in ['partnership', 'collaboration']):
                    catalyst_type = CatalystType.PARTNERSHIP
                    break
                elif any(contract_word in keyword.lower() for contract_word in ['contract', 'deal', 'order']):
                    catalyst_type = CatalystType.CONTRACT
                    break
            
            return NewsAnalysis(
                ticker=ticker,
                date=datetime.now().date(),
                sentiment=sentiment,
                catalyst_type=catalyst_type,
                confidence_score=sentiment_result.confidence,
                impact_score=sentiment_result.confidence * 0.8,
                keywords=sentiment_result.positive_keywords[:5] + sentiment_result.negative_keywords[:5],
                source_text=news_text[:200]
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing ticker news for {ticker}: {e}")
            return None
    
    def calculate_ml_score(self, ticker: str) -> float:
        """Calcular score ML usando datos históricos reales"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                # Obtener datos históricos del ticker
                trades = conn.execute("""
                    SELECT pnl, strategy, entry_time FROM trades 
                    WHERE symbol = ? AND pnl IS NOT NULL 
                    ORDER BY entry_time DESC LIMIT 10
                """, (ticker,)).fetchall()
                
                if not trades:
                    # Sin historial, score neutral
                    return 0.5
                
                # Calcular métricas de rendimiento
                pnls = [float(trade[0]) for trade in trades]
                win_rate = len([pnl for pnl in pnls if pnl > 0]) / len(pnls)
                avg_pnl = sum(pnls) / len(pnls)
                
                # Score base en win rate (0.0 - 1.0)
                score = win_rate
                
                # Ajustar por PnL promedio
                if avg_pnl > 50:
                    score += 0.2
                elif avg_pnl > 0:
                    score += 0.1
                elif avg_pnl < -50:
                    score -= 0.2
                elif avg_pnl < 0:
                    score -= 0.1
                
                # Ajustar por volumen de trades (más datos = más confianza)
                volume_boost = min(0.1, len(trades) * 0.01)
                score += volume_boost
                
                # Clamp entre 0.1 y 0.9
                return max(0.1, min(0.9, score))
                
        except Exception as e:
            self.logger.error(f"Error calculating ML score for {ticker}: {e}")
            return 0.5
    
    def should_auto_add_ticker(self, ticker: str, config: 'ScannerConfig') -> bool:
        """Determinar auto-add usando ML score y configuración"""
        try:
            if not config or not config.learning_enabled:
                return False
                
            ml_score = self.calculate_ml_score(ticker)
            return ml_score >= config.auto_add_threshold
            
        except Exception as e:
            self.logger.error(f"Error checking auto-add for {ticker}: {e}")
            return False