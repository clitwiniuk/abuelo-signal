#!/usr/bin/env python3
"""
Scanner Intelligence System
Sistema de aprendizaje continuo para scanner con base de datos persistente
"""

import sqlite3
import json
import re
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
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
    was_profitable: Optional[bool]
    hold_duration_minutes: Optional[int]
    strategy_used: str
    notes: str

@dataclass 
class AdvancedTradingResult:
    """Advanced trading result based on professional trade journal template"""
    # Basic trade info
    ticker: str
    trade_date: date
    pnl: Optional[float]
    
    # Trade categorization (your playbook categories)
    trade_category: str  # "Gap Play", "VWAP Reclaim", "News Catalyst", "Breakout", etc.
    
    # Context analysis
    context_type: str  # "Breaking News", "No News", "Earnings", "FDA", "Market Wide"
    market_context: str  # "Bull Market", "Bear Market", "Sideways", "High Vol", "Low Vol"
    why_in_play: str  # Reason ticker was in-play for you
    
    # Fundamental data (auto-populated when available)
    market_cap: Optional[str] = None  # "Small <500M", "Mid 500M-2B", "Large >2B"
    float_size: Optional[str] = None  # "Low <10M", "Medium 10-50M", "High >50M"
    short_interest: Optional[str] = None  # "Low <10%", "Medium 10-30%", "High >30%"
    fundamental_notes: str = ""
    
    # Technical analysis
    daily_chart_analysis: str = ""
    daily_volume_context: str = ""  # "Normal", "2x Average", "5x Average", "10x+ Massive"
    intraday_chart_analysis: str = ""
    intraday_volume_context: str = ""
    
    # Level 2 / Order book (COMMENTED - for future Level 2 integration)
    # level2_analysis: str = ""
    # major_players: str = ""  # "Heavy buyers", "Major sellers", "Balanced", "Thin book"
    # bid_ask_behavior: str = ""  # "More offers taken", "More bids hit", "Balanced"
    
    # Execution analysis
    how_you_traded: str = ""
    followed_system: bool = True
    emotional_impact: str = "Neutral"  # "Positive", "Negative", "Neutral"
    sizing_appropriate: bool = True
    execution_quality: str = "Good"  # "Excellent", "Good", "Poor"
    
    # Social/collaborative insights (OPTIONAL)
    how_others_traded: str = ""
    others_thoughts: str = ""
    
    # Reflection & improvement
    how_should_have_traded: str = ""
    ideal_sizing: str = ""
    ideal_entry: str = ""
    ideal_exit: str = ""
    reasons_for_audible: str = ""
    
    # Learning & technology
    how_find_more_opps: str = ""
    technology_usage: str = ""
    collaboration_insights: str = ""
    
    # Lessons learned
    solutions_learned: str = ""
    key_takeaways: str = ""
    changes_to_make: str = ""
    
    # System fields
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    hold_duration_minutes: Optional[int] = None
    strategy_used: str = ""
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class AutoCategorizer:
    """Intelligent auto-categorization system for trades"""
    
    def __init__(self):
        self.logger = logging.getLogger("AutoCategorizer")
    
    def categorize_trade_automatically(self, ticker: str, entry_price: float, 
                                     exit_price: Optional[float], trade_date: date,
                                     hold_duration_minutes: Optional[int],
                                     strategy_used: str, pnl: Optional[float]) -> AdvancedTradingResult:
        """Automatically categorize a trade based on available data"""
        
        try:
            # Get market data for analysis
            gap_percent = self._calculate_gap_percent(ticker, trade_date, entry_price)
            volume_context = self._analyze_volume_context(ticker, trade_date)
            news_context = self._detect_news_context(ticker, trade_date)
            market_context = self._analyze_market_context(trade_date)
            
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
            
            # Determine emotional impact
            emotional_impact = self._determine_emotional_impact(pnl, hold_duration_minutes)
            
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
                emotional_impact=emotional_impact,
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
                trade_category="System Trade",
                context_type="Unknown",
                market_context="Standard Hours",
                why_in_play="System-generated trade"
            )
    
    def _calculate_gap_percent(self, ticker: str, trade_date: date, entry_price: float) -> float:
        """Calculate gap percentage from previous close"""
        # This would ideally use real market data
        # For now, simulate based on entry price patterns
        try:
            # Mock calculation - in reality would compare to previous close
            if entry_price > 10:
                return 2.5  # Assume moderate gap for higher priced stocks
            else:
                return 5.0  # Assume higher gap for lower priced stocks
        except:
            return 0.0
    
    def _analyze_volume_context(self, ticker: str, trade_date: date) -> str:
        """Analyze volume context for the ticker"""
        # This would ideally analyze real volume data
        # For now, simulate based on patterns
        import random
        volume_multipliers = ["Normal", "2x Average", "5x Average", "10x+ Massive"]
        return random.choice(volume_multipliers)
    
    def _detect_news_context(self, ticker: str, trade_date: date) -> str:
        """Detect if there was news on the trade date"""
        # This would ideally check news databases
        # For now, simulate
        import random
        news_types = ["No News", "Breaking News", "Earnings", "FDA", "Market Wide"]
        return random.choice(news_types[:2])  # Mostly No News or Breaking News
    
    def _analyze_market_context(self, trade_date: date) -> str:
        """Analyze overall market context"""
        from datetime import datetime
        current_time = datetime.now()
        hour = current_time.hour
        
        if 9 <= hour < 10:
            return "Market Open"
        elif 10 <= hour < 12:
            return "Morning Session"
        elif 12 <= hour < 14:
            return "Lunch Hour"
        elif 14 <= hour < 16:
            return "Afternoon Session"
        else:
            return "After Hours"
    
    def _determine_trade_category(self, gap_percent: float, volume_context: str, 
                                news_context: str, strategy_used: str,
                                entry_price: float, exit_price: Optional[float]) -> str:
        """Determine trade category based on data"""
        
        # News-based categories
        if "news" in news_context.lower() or "earnings" in news_context.lower():
            return "News Catalyst"
        if "fda" in news_context.lower():
            return "FDA Play"
        
        # Gap-based categories
        if gap_percent > 5:
            return "Gap Play"
        
        # Volume-based categories
        if "5x" in volume_context or "10x" in volume_context:
            return "Volume Spike"
        
        # Strategy-based categories
        if "vwap" in strategy_used.lower():
            return "VWAP Reclaim"
        if "breakout" in strategy_used.lower():
            return "Breakout"
        if "orb" in strategy_used.lower():
            return "ORB Play"
        if "macdv" in strategy_used.lower():
            return "Technical Setup"
        
        # Default
        return "Technical Setup"
    
    def _determine_context_type(self, news_context: str, gap_percent: float, volume_context: str) -> str:
        """Determine the context type"""
        if "breaking" in news_context.lower():
            return "Breaking News"
        elif "earnings" in news_context.lower():
            return "Earnings"
        elif "fda" in news_context.lower():
            return "FDA Approval/Rejection"
        elif gap_percent > 10 or "10x" in volume_context:
            return "Market Wide Move"
        else:
            return "No News"
    
    def _analyze_execution_quality(self, entry_price: float, exit_price: Optional[float],
                                 hold_duration_minutes: Optional[int], pnl: Optional[float]) -> str:
        """Analyze execution quality based on results"""
        if not pnl or not hold_duration_minutes:
            return "Good"
        
        # Quick profitable trades = excellent
        if pnl > 0 and hold_duration_minutes < 30:
            return "Excellent"
        
        # Profitable but took long = good
        elif pnl > 0 and hold_duration_minutes < 120:
            return "Good"
        
        # Profitable but very long = fair
        elif pnl > 0:
            return "Fair"
        
        # Quick losses = fair (cut losses quickly)
        elif pnl < 0 and hold_duration_minutes < 15:
            return "Fair"
        
        # Long losses = poor
        else:
            return "Poor"
    
    def _determine_emotional_impact(self, pnl: Optional[float], hold_duration_minutes: Optional[int]) -> str:
        """Determine emotional impact"""
        if not pnl:
            return "Neutral"
        
        # Big wins = positive
        if pnl > 500:
            return "Positive"
        
        # Big losses = negative
        elif pnl < -200:
            return "Negative"
        
        # Everything else neutral
        else:
            return "Neutral"
    
    def _generate_why_in_play(self, trade_category: str, gap_percent: float, volume_context: str) -> str:
        """Generate why this ticker was in play"""
        reasons = []
        
        if gap_percent > 5:
            reasons.append(f"{gap_percent:.1f}% gap")
        
        if "5x" in volume_context or "10x" in volume_context:
            reasons.append(f"{volume_context} volume")
        
        if trade_category == "News Catalyst":
            reasons.append("news catalyst")
        
        if not reasons:
            reasons.append("technical setup")
        
        return ", ".join(reasons)

@dataclass
class ScannerConfig:
    sentiment_filter: str  # "ONLY_POSITIVE" or "POSITIVE_NEUTRAL"
    max_float: int
    min_gap_percent: float
    min_volume: int
    auto_add_threshold: float  # ML score threshold for auto-add
    learning_enabled: bool

class ScannerIntelligence:
    """Sistema inteligente de scanner con aprendizaje continuo"""
    
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
            CatalystType.CONTRACT: ["contract", "award", "win", "agreement"],
            CatalystType.BREAKTHROUGH: ["breakthrough", "innovation", "patent", "technology"],
            CatalystType.CRYPTO: ["bitcoin", "crypto", "blockchain", "digital"],
            CatalystType.OIL_GAS: ["oil", "gas", "drilling", "energy", "barrel"],
            CatalystType.CLINICAL: ["clinical", "patient", "treatment", "therapy"],
            CatalystType.ACQUISITION: ["acquisition", "acquired", "purchase"],
            CatalystType.INNOVATION: ["innovation", "launch", "product", "development"]
        }
        
        self.sentiment_indicators = {
            SentimentType.POSITIVE: [
                "beat", "exceed", "strong", "growth", "bullish", "upgrade", 
                "approval", "breakthrough", "success", "win", "gain", "rise",
                "positive", "outperform", "target raised"
            ],
            SentimentType.NEGATIVE: [
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
                        emotional_impact TEXT,
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
    
    def setup_database(self):
        """Configurar base de datos para aprendizaje"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de análisis de noticias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                sentiment TEXT NOT NULL,
                catalyst_type TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                impact_score REAL NOT NULL,
                keywords TEXT NOT NULL,
                source_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de resultados de trading
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                trade_date DATE NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                pnl REAL,
                was_profitable BOOLEAN,
                hold_duration_minutes INTEGER,
                strategy_used TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de patrones aprendidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                success_rate REAL NOT NULL,
                confidence REAL NOT NULL,
                sample_size INTEGER NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de configuración
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scanner_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de resultados avanzados (auto-categorización)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS advanced_trading_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                trade_date DATE NOT NULL,
                pnl REAL,
                trade_category TEXT NOT NULL,
                context_type TEXT NOT NULL,
                market_context TEXT NOT NULL,
                why_in_play TEXT,
                daily_volume_context TEXT,
                intraday_volume_context TEXT,
                daily_chart_analysis TEXT,
                intraday_chart_analysis TEXT,
                how_you_traded TEXT,
                followed_system BOOLEAN,
                emotional_impact TEXT,
                sizing_appropriate BOOLEAN,
                execution_quality TEXT,
                how_should_have_traded TEXT,
                key_takeaways TEXT,
                changes_to_make TEXT,
                entry_price REAL,
                exit_price REAL,
                hold_duration_minutes INTEGER,
                strategy_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def analyze_ticker_news(self, ticker: str, news_text: str = "") -> Optional[NewsAnalysis]:
        """Analizar noticias de un ticker"""
        
        if not news_text:
            # Si no hay texto de noticias, retornar análisis básico
            return NewsAnalysis(
                ticker=ticker,
                date=date.today(),
                sentiment=SentimentType.NEUTRAL,
                catalyst_type=CatalystType.OTHER,
                confidence_score=0.1,
                impact_score=0.1,
                keywords=[],
                source_text=""
            )
        
        text_lower = news_text.lower()
        
        # Detectar tipo de catalizador
        catalyst_type = CatalystType.OTHER
        catalyst_confidence = 0.0
        
        for cat_type, keywords in self.catalyst_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > 0:
                new_confidence = matches / len(keywords)
                if new_confidence > catalyst_confidence:
                    catalyst_type = cat_type
                    catalyst_confidence = new_confidence
        
        # Detectar sentimiento
        positive_score = sum(1 for word in self.sentiment_indicators[SentimentType.POSITIVE] if word in text_lower)
        negative_score = sum(1 for word in self.sentiment_indicators[SentimentType.NEGATIVE] if word in text_lower)
        
        if positive_score > negative_score:
            sentiment = SentimentType.POSITIVE
            sentiment_confidence = positive_score / (positive_score + negative_score + 1)
        elif negative_score > positive_score:
            sentiment = SentimentType.NEGATIVE
            sentiment_confidence = negative_score / (positive_score + negative_score + 1)
        else:
            sentiment = SentimentType.NEUTRAL
            sentiment_confidence = 0.5
        
        # Calcular scores finales
        confidence_score = (catalyst_confidence + sentiment_confidence) / 2
        impact_score = min(1.0, catalyst_confidence * 1.5 + sentiment_confidence * 0.5)
        
        # Extraer keywords relevantes
        keywords = []
        for cat_keywords in self.catalyst_keywords.values():
            keywords.extend([kw for kw in cat_keywords if kw in text_lower])
        keywords = list(set(keywords))[:10]  # Máximo 10 keywords únicos
        
        analysis = NewsAnalysis(
            ticker=ticker,
            date=date.today(),
            sentiment=sentiment,
            catalyst_type=catalyst_type,
            confidence_score=confidence_score,
            impact_score=impact_score,
            keywords=keywords,
            source_text=news_text[:500]  # Limitar texto
        )
        
        # Guardar en base de datos
        self._store_news_analysis(analysis)
        
        return analysis
    
    def _store_news_analysis(self, analysis: NewsAnalysis):
        """Guardar análisis en base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO news_analysis 
            (ticker, date, sentiment, catalyst_type, confidence_score, 
             impact_score, keywords, source_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis.ticker,
            analysis.date,
            analysis.sentiment.value,
            analysis.catalyst_type.value,
            analysis.confidence_score,
            analysis.impact_score,
            json.dumps(analysis.keywords),
            analysis.source_text
        ))
        
        conn.commit()
        conn.close()
    
    def calculate_ml_score(self, ticker: str, technical_data: Dict = None) -> float:
        """Calcular score ML para un ticker basado en histórico"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Obtener análisis reciente del ticker
        cursor.execute('''
            SELECT sentiment, catalyst_type, confidence_score, impact_score
            FROM news_analysis 
            WHERE ticker = ? AND date >= date('now', '-7 days')
            ORDER BY created_at DESC LIMIT 1
        ''', (ticker,))
        
        news_result = cursor.fetchone()
        
        # Obtener patrones históricos exitosos
        cursor.execute('''
            SELECT pattern_data, success_rate, confidence
            FROM learned_patterns
            WHERE confidence > 0.3
            ORDER BY success_rate DESC
        ''')
        
        patterns = cursor.fetchall()
        conn.close()
        
        base_score = 0.0
        
        # Score basado en noticias recientes
        if news_result:
            sentiment, catalyst_type, confidence, impact = news_result
            
            # Bonus por sentimiento positivo
            if sentiment == SentimentType.POSITIVE.value:
                base_score += 0.4 * confidence
            elif sentiment == SentimentType.NEUTRAL.value:
                base_score += 0.2 * confidence
            
            # Bonus por impacto esperado
            base_score += impact * 0.3
            
            # Bonus por tipo de catalizador exitoso (basado en patrones)
            for pattern_data_json, success_rate, pattern_confidence in patterns:
                try:
                    pattern_data = json.loads(pattern_data_json)
                    if (pattern_data.get('catalyst_type') == catalyst_type and 
                        pattern_confidence > 0.5):
                        base_score += success_rate * 0.3
                        break
                except:
                    continue
        
        # Score basado en datos técnicos (si están disponibles)
        if technical_data:
            volume_ratio = technical_data.get('volume_ratio', 1.0)
            gap_percent = technical_data.get('gap_percent', 0.0)
            
            # Bonus por volumen alto
            if volume_ratio > 2.0:
                base_score += 0.2
            elif volume_ratio > 1.5:
                base_score += 0.1
            
            # Bonus por gap significativo
            if gap_percent > 15:
                base_score += 0.2
            elif gap_percent > 10:
                base_score += 0.1
        
        return min(1.0, max(0.0, base_score))
    
    def should_auto_add_ticker(self, ticker: str, config: ScannerConfig) -> bool:
        """Determinar si un ticker debe añadirse automáticamente"""
        
        if not config.learning_enabled:
            return False
        
        # Obtener análisis reciente
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sentiment, confidence_score, impact_score
            FROM news_analysis 
            WHERE ticker = ? AND date >= date('now', '-1 days')
            ORDER BY created_at DESC LIMIT 1
        ''', (ticker,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return False
        
        sentiment, confidence, impact = result
        
        # Aplicar filtro de sentimiento
        if config.sentiment_filter == "ONLY_POSITIVE":
            if sentiment != SentimentType.POSITIVE.value:
                return False
        elif config.sentiment_filter == "POSITIVE_NEUTRAL":
            if sentiment == SentimentType.NEGATIVE.value:
                return False
        
        # Calcular score ML
        ml_score = self.calculate_ml_score(ticker)
        
        # Auto-add si supera el threshold
        return ml_score >= config.auto_add_threshold
    
    def add_trading_result(self, result: TradingResult):
        """Añadir resultado de trading para aprendizaje"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trading_results 
            (ticker, trade_date, entry_price, exit_price, pnl, was_profitable,
             hold_duration_minutes, strategy_used, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.ticker,
            result.trade_date,
            result.entry_price,
            result.exit_price,
            result.pnl,
            result.was_profitable,
            result.hold_duration_minutes,
            result.strategy_used,
            result.notes
        ))
        
        conn.commit()
        conn.close()
        
        # 🤖 AUTO-CATEGORIZATION: Generate advanced analysis automatically
        try:
            auto_categorizer = AutoCategorizer()
            advanced_result = auto_categorizer.categorize_trade_automatically(
                ticker=result.ticker,
                entry_price=result.entry_price,
                exit_price=result.exit_price,
                trade_date=result.trade_date,
                hold_duration_minutes=result.hold_duration_minutes,
                strategy_used=result.strategy_used,
                pnl=result.pnl
            )
            
            # Store advanced categorization
            self._store_advanced_trading_result(advanced_result)
            
            self.logger.info(f"🤖 Auto-categorized {result.ticker} as {advanced_result.trade_category} ({advanced_result.execution_quality} execution)")
            
        except Exception as e:
            self.logger.error(f"Error in auto-categorization for {result.ticker}: {e}")
        
        # Actualizar patrones aprendidos
        self._update_learned_patterns()
    
    def _store_advanced_trading_result(self, advanced_result: AdvancedTradingResult):
        """Store advanced trading result with auto-categorization"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO advanced_trading_results 
            (ticker, trade_date, pnl, trade_category, context_type, market_context,
             why_in_play, daily_volume_context, intraday_volume_context,
             daily_chart_analysis, intraday_chart_analysis, how_you_traded,
             followed_system, emotional_impact, sizing_appropriate, execution_quality,
             how_should_have_traded, key_takeaways, changes_to_make,
             entry_price, exit_price, hold_duration_minutes, strategy_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            advanced_result.ticker,
            advanced_result.trade_date,
            advanced_result.pnl,
            advanced_result.trade_category,
            advanced_result.context_type,
            advanced_result.market_context,
            advanced_result.why_in_play,
            advanced_result.daily_volume_context,
            advanced_result.intraday_volume_context,
            advanced_result.daily_chart_analysis,
            advanced_result.intraday_chart_analysis,
            advanced_result.how_you_traded,
            advanced_result.followed_system,
            advanced_result.emotional_impact,
            advanced_result.sizing_appropriate,
            advanced_result.execution_quality,
            advanced_result.how_should_have_traded,
            advanced_result.key_takeaways,
            advanced_result.changes_to_make,
            advanced_result.entry_price,
            advanced_result.exit_price,
            advanced_result.hold_duration_minutes,
            advanced_result.strategy_used
        ))
        
        conn.commit()
        conn.close()
    
    def get_advanced_trading_results(self, limit: int = 50) -> List[AdvancedTradingResult]:
        """Get recent advanced trading results"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ticker, trade_date, pnl, trade_category, context_type, market_context,
                   why_in_play, daily_volume_context, intraday_volume_context,
                   daily_chart_analysis, intraday_chart_analysis, how_you_traded,
                   followed_system, emotional_impact, sizing_appropriate, execution_quality,
                   how_should_have_traded, key_takeaways, changes_to_make,
                   entry_price, exit_price, hold_duration_minutes, strategy_used, created_at
            FROM advanced_trading_results
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append(AdvancedTradingResult(
                ticker=row[0],
                trade_date=row[1],
                pnl=row[2],
                trade_category=row[3],
                context_type=row[4],
                market_context=row[5],
                why_in_play=row[6] or "",
                daily_volume_context=row[7] or "",
                intraday_volume_context=row[8] or "",
                daily_chart_analysis=row[9] or "",
                intraday_chart_analysis=row[10] or "",
                how_you_traded=row[11] or "",
                followed_system=row[12] if row[12] is not None else True,
                emotional_impact=row[13] or "Neutral",
                sizing_appropriate=row[14] if row[14] is not None else True,
                execution_quality=row[15] or "Good",
                how_should_have_traded=row[16] or "",
                key_takeaways=row[17] or "",
                changes_to_make=row[18] or "",
                entry_price=row[19],
                exit_price=row[20],
                hold_duration_minutes=row[21],
                strategy_used=row[22] or "",
                created_at=row[23]
            ))
        
        conn.close()
        return results
    
    def _update_learned_patterns(self):
        """Actualizar patrones basado en resultados históricos"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Analizar performance por tipo de catalizador (reducir threshold mínimo)
        cursor.execute('''
            SELECT na.catalyst_type, na.sentiment,
                   COUNT(*) as total_trades,
                   SUM(CASE WHEN tr.was_profitable = 1 THEN 1 ELSE 0 END) as profitable_trades,
                   AVG(tr.pnl) as avg_pnl,
                   AVG(na.confidence_score) as avg_confidence,
                   AVG(na.impact_score) as avg_impact
            FROM news_analysis na
            JOIN trading_results tr ON na.ticker = tr.ticker 
                AND na.date = tr.trade_date
            WHERE tr.trade_date >= date('now', '-30 days')
            GROUP BY na.catalyst_type, na.sentiment
            HAVING COUNT(*) >= 2
        ''')
        
        patterns = cursor.fetchall()
        
        for pattern in patterns:
            (catalyst_type, sentiment, total_trades, profitable_trades, 
             avg_pnl, avg_confidence, avg_impact) = pattern
            
            success_rate = profitable_trades / total_trades if total_trades > 0 else 0
            confidence = min(1.0, total_trades / 10.0)  # Más trades = más confianza
            
            pattern_data = {
                'catalyst_type': catalyst_type,
                'sentiment': sentiment,
                'avg_pnl': avg_pnl,
                'avg_confidence': avg_confidence,
                'avg_impact': avg_impact,
                'sample_size': total_trades
            }
            
            pattern_key = f"{catalyst_type}_{sentiment}"
            
            cursor.execute('''
                INSERT OR REPLACE INTO learned_patterns 
                (pattern_type, pattern_data, success_rate, confidence, sample_size)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                pattern_key,
                json.dumps(pattern_data),
                success_rate,
                confidence,
                total_trades
            ))
        
        conn.commit()
        conn.close()
    
    def get_learning_stats(self) -> Dict:
        """Obtener estadísticas de aprendizaje"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Estadísticas generales
        cursor.execute('SELECT COUNT(*) FROM news_analysis')
        total_news = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trading_results')
        total_trades = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM trading_results 
            WHERE was_profitable = 1
        ''')
        profitable_trades = cursor.fetchone()[0]
        
        # Mejores patrones
        cursor.execute('''
            SELECT pattern_type, success_rate, confidence, sample_size
            FROM learned_patterns
            WHERE confidence > 0.5
            ORDER BY success_rate DESC LIMIT 5
        ''')
        best_patterns = cursor.fetchall()
        
        conn.close()
        
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_news_analyzed': total_news,
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': win_rate,
            'best_patterns': best_patterns,
            'learning_active': total_trades > 0
        }
    
    def save_config(self, config: ScannerConfig):
        """Guardar configuración"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO scanner_config (config_data)
            VALUES (?)
        ''', (json.dumps(asdict(config)),))
        
        conn.commit()
        conn.close()
    
    def load_config(self) -> Optional[ScannerConfig]:
        """Cargar configuración más reciente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT config_data FROM scanner_config
            ORDER BY created_at DESC LIMIT 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            try:
                config_dict = json.loads(result[0])
                return ScannerConfig(**config_dict)
            except:
                pass
        
        # Configuración por defecto (thresholds más realistas)
        return ScannerConfig(
            sentiment_filter="ONLY_POSITIVE",
            max_float=100_000_000,
            min_gap_percent=10.0,
            min_volume=500_000,
            auto_add_threshold=0.3,  # Threshold más bajo para permitir más auto-adds
            learning_enabled=True
        )

# === TESTING ===

def test_scanner_intelligence():
    """Test del sistema de inteligencia"""
    
    logger.info("🧪 Testing Scanner Intelligence")
    logger.info("=" * 50)
    
    intelligence = ScannerIntelligence()
    
    # Test news analysis
    test_news = "Company XYZ beats earnings expectations with strong Q3 results. FDA approval expected soon."
    analysis = intelligence.analyze_ticker_news("XYZ", test_news)
    
    logger.info(f"📰 News Analysis for XYZ:")
    logger.info(f"   Sentiment: {analysis.sentiment.value}")
    logger.info(f"   Catalyst: {analysis.catalyst_type.value}")
    logger.info(f"   Confidence: {analysis.confidence_score:.2f}")
    logger.info(f"   Impact: {analysis.impact_score:.2f}")
    
    # Test ML score
    ml_score = intelligence.calculate_ml_score("XYZ")
    logger.info(f"   ML Score: {ml_score:.2f}")
    
    # Test config
    config = intelligence.load_config()
    logger.info(f"\n⚙️ Default Config:")
    logger.info(f"   Sentiment Filter: {config.sentiment_filter}")
    logger.info(f"   Auto-add Threshold: {config.auto_add_threshold}")
    
    # Test stats
    stats = intelligence.get_learning_stats()
    logger.info(f"\n📊 Learning Stats:")
    logger.info(f"   News Analyzed: {stats['total_news_analyzed']}")
    logger.info(f"   Total Trades: {stats['total_trades']}")
    logger.info(f"   Win Rate: {stats['win_rate']:.1f}%")
    
    logger.info(f"\n✅ Scanner Intelligence test completed")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_scanner_intelligence()