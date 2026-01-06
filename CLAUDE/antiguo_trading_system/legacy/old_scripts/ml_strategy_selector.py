# strategies/ml_strategy_selector.py
"""
ML-Based Strategy Selector - Contextual Multi-Armed Bandit
Sistema de selección inteligente de estrategias usando Machine Learning
para optimizar el matching estrategia-ticker basado en performance real.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
import pickle
import os
import sqlite3
from dataclasses import dataclass, asdict
import json

try:
    from core.interfaces import MarketData, Signal
except ImportError:
    from collections import namedtuple
    MarketData = namedtuple('MarketData', ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
    Signal = namedtuple('Signal', ['symbol', 'signal_type', 'price', 'confidence'])

logger = logging.getLogger(__name__)

@dataclass
class ScannerEventContext:
    """Contexto basado en datos reales de scanner events"""
    # Datos básicos del evento
    id_event: int
    symbol: str
    timestamp: str
    
    # Datos reales del trade
    entry_price: float
    quantity: int
    daily_win_rate: float   # Win rate del día para contexto de mercado
    daily_pnl: float        # PnL acumulado del día
    
    # Contexto temporal derivado
    hour_of_day: float
    day_of_week: int
    minutes_from_open: int
    
    def to_feature_vector(self) -> np.ndarray:
        """Convierte el contexto a vector de features para ML basado en datos reales con trend features"""
        # Original features
        base_features = [
            self.entry_price,               # Precio de entrada real
            np.log(max(1, self.quantity)), # Log cantidad (tamaño de posición)
            self.daily_win_rate,           # Win rate del día (contexto de mercado)
            self.daily_pnl,                # PnL acumulado del día
            self.hour_of_day,              # Hora del día
            float(self.day_of_week),       # Día de la semana
            self.minutes_from_open,        # Minutos desde apertura
        ]
        
        # NEW: Trend features (loaded from database or calculated)
        trend_features = [
            getattr(self, 'price_momentum', 1.0),      # Price vs recent average
            getattr(self, 'relative_position', 0.5),   # Position in recent range
            getattr(self, 'symbol_strength', 0.0),     # Recent symbol performance
            getattr(self, 'recent_high_5d', self.entry_price) / self.entry_price,  # Distance from recent high
            getattr(self, 'recent_low_5d', self.entry_price) / self.entry_price,   # Distance from recent low
        ]
        
        return np.array(base_features + trend_features, dtype=np.float32)
    
    @classmethod
    def from_trade_data(cls, trade_data: dict) -> 'ScannerEventContext':
        """Crear contexto desde datos reales de trades con trend features"""
        timestamp = pd.to_datetime(trade_data['timestamp'])
        
        # Calcular contexto temporal
        hour_of_day = timestamp.hour + timestamp.minute / 60.0
        day_of_week = timestamp.weekday()
        market_open = timestamp.replace(hour=9, minute=30, second=0, microsecond=0)
        minutes_from_open = max(0, (timestamp - market_open).total_seconds() / 60)
        
        # Create base context
        context = cls(
            id_event=trade_data['id_event'],
            symbol=trade_data['symbol'],
            timestamp=trade_data['timestamp'],
            entry_price=trade_data['entry_price'],
            quantity=trade_data['quantity'],
            daily_win_rate=trade_data.get('daily_win_rate', 0.5),  # Default to 50%
            daily_pnl=trade_data.get('daily_pnl', 0.0),
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            minutes_from_open=int(minutes_from_open)
        )
        
        # Load trend features from trade data if available
        context.price_momentum = trade_data.get('price_momentum', 1.0)
        context.relative_position = trade_data.get('relative_position', 0.5) 
        context.symbol_strength = trade_data.get('symbol_strength', 0.0)
        context.recent_high_5d = trade_data.get('recent_high_5d', trade_data['entry_price'])
        context.recent_low_5d = trade_data.get('recent_low_5d', trade_data['entry_price'])
        context.recent_avg_price = trade_data.get('recent_avg_price', trade_data['entry_price'])
        context.volume_trend = trade_data.get('volume_trend', 1.0)
        context.market_context = trade_data.get('market_context', 'NEUTRAL')
        
        return context
    
    @classmethod
    def from_scanner_data(cls, event_data: dict) -> 'ScannerEventContext':
        """Crear contexto desde datos de scanner events (legacy)"""
        timestamp = pd.to_datetime(event_data['timestamp'])
        
        # Calcular contexto temporal
        hour_of_day = timestamp.hour + timestamp.minute / 60.0
        day_of_week = timestamp.weekday()
        market_open = timestamp.replace(hour=9, minute=30, second=0, microsecond=0)
        minutes_from_open = max(0, (timestamp - market_open).total_seconds() / 60)
        
        return cls(
            id_event=event_data['id_event'],
            symbol=event_data['ticker'],
            timestamp=event_data['timestamp'],
            entry_price=event_data['precio'],  # Map to entry_price
            quantity=1000,  # Default quantity for scanner data
            daily_win_rate=0.5,  # Default market context
            daily_pnl=0.0,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            minutes_from_open=int(minutes_from_open)
        )

@dataclass
class TickerContext:
    """Contexto completo de un ticker para ML"""
    symbol: str
    
    # Características técnicas básicas
    current_price: float
    avg_volume_10: float  # Volumen promedio últimos 10 bars
    avg_volume_50: float  # Volumen promedio últimos 50 bars
    volatility_10: float  # Volatilidad últimos 10 bars
    volatility_50: float  # Volatilidad últimos 50 bars
    
    # Patrones de precio
    price_change_1h: float  # Cambio precio última hora
    price_change_4h: float  # Cambio precio últimas 4 horas
    rsi_14: float  # RSI 14 períodos
    
    # Patrones de volumen
    volume_ratio_current: float  # Volumen actual vs promedio
    volume_spike_frequency: float  # Frecuencia de picos de volumen
    
    # Contexto temporal
    hour_of_day: float  # Hora del día (9.5 = 9:30 AM)
    minutes_from_open: int  # Minutos desde apertura
    is_first_hour: bool  # Primera hora de trading
    is_last_hour: bool  # Última hora de trading
    
    # Contexto de mercado (opcional)
    market_trend: float  # -1 a 1 (bearish a bullish)
    sector_performance: float  # Performance del sector hoy
    
    # Performance histórica
    breakout_success_rate: float  # Tasa éxito breakouts históricos
    mean_reversion_tendency: float  # Tendencia a mean reversion
    
    def to_feature_vector(self) -> np.ndarray:
        """Convierte el contexto a vector de features para ML"""
        features = [
            self.current_price,
            self.avg_volume_10,
            self.avg_volume_50,
            self.volatility_10,
            self.volatility_50,
            self.price_change_1h,
            self.price_change_4h,
            self.rsi_14,
            self.volume_ratio_current,
            self.volume_spike_frequency,
            self.hour_of_day,
            self.minutes_from_open,
            float(self.is_first_hour),
            float(self.is_last_hour),
            self.market_trend,
            self.sector_performance,
            self.breakout_success_rate,
            self.mean_reversion_tendency
        ]
        return np.array(features, dtype=np.float32)

@dataclass
class StrategyPerformance:
    """Tracking de performance por estrategia"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    win_rate: float = 0.0
    last_updated: datetime = None
    
    def update(self, pnl: float):
        """Actualiza métricas con nuevo trade"""
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
        self.total_pnl += pnl
        self.avg_pnl = self.total_pnl / self.total_trades
        self.win_rate = self.winning_trades / self.total_trades
        self.last_updated = datetime.now()

class ContextualBandit:
    """
    Contextual Multi-Armed Bandit para selección de estrategias
    Usa Thompson Sampling con regresión lineal contextual
    """
    
    def __init__(self, strategies: List[str], feature_dim: int = 12, alpha: float = 10.0, auto_retrain: bool = True):  # ✅ Enhanced with trend features
        self.strategies = strategies
        self.feature_dim = feature_dim
        self.alpha = alpha  # Parámetro de regularización
        self.auto_retrain = auto_retrain  # Auto-retraining enabled
        
        # Database management
        self.primary_db = "trading_data.db"      # Production database
        self.fallback_db = "database_quality.db"  # Development/historical database
        self.current_db = None
        self.last_training_count = 0  # Track when we last trained
        self.retrain_threshold = self._load_retrain_threshold()  # Load from config or default
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        # Parámetros del modelo por estrategia (Thompson Sampling)
        self.A = {}  # Matriz de diseño A = X^T * X + alpha * I
        self.b = {}  # Vector b = X^T * y
        self.theta = {}  # Parámetros estimados
        
        # Inicializar matrices para cada estrategia
        for strategy in strategies:
            self.A[strategy] = np.eye(feature_dim) * alpha
            self.b[strategy] = np.zeros(feature_dim)
            self.theta[strategy] = np.zeros(feature_dim)
        
        # Initialize strategy stats after class definition is complete
        self._initialize_strategy_stats()
    
    def _load_retrain_threshold(self) -> int:
        """Load retrain threshold from config.ini or use default"""
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read('config.ini')
            threshold = config.getint('GLOBAL', 'ml_retrain_threshold', fallback=50)
            logger.info(f"🎯 ML retrain threshold loaded from config: {threshold}")
            return threshold
        except Exception as e:
            logger.warning(f"Could not load retrain threshold from config: {e}. Using default: 50")
            return 50
    
    def _initialize_strategy_stats(self):
        """Initialize strategy stats after StrategyPerformance is available"""
        self.strategy_stats = {s: StrategyPerformance(s) for s in self.strategies}
        self.exploration_rate = 0.2  # ✅ 20% exploration (más conservador)
        self.min_trades_per_strategy = 10  # ✅ Mínimo 10 trades antes de confiar en el modelo
        
        self.logger = logging.getLogger(f"{__name__}.ContextualBandit")
    
    def select_strategy(self, context: TickerContext,
                       available_strategies: Optional[List[str]] = None) -> str:
        """
        Selecciona la mejor estrategia para el contexto dado
        usando Thompson Sampling
        """
        if available_strategies is None:
            available_strategies = self.strategies

        features = context.to_feature_vector()

        # DIMENSION CHECK: Fix matmul error by ensuring feature vector matches expected dimension
        if len(features) != self.feature_dim:
            # Dimension mismatch - log warning and fall back to VALIDATED selection
            self.logger.warning(f"⚠️ Feature dimension mismatch: got {len(features)}, expected {self.feature_dim}. Using VALIDATED fallback selection.")
            # SECURE FALLBACK: Use intelligent fallback that respects strategy validations
            return self._secure_fallback_strategy_selection(available_strategies, features)

        # Estrategias con pocos datos -> exploration forzada
        undertrained_strategies = [
            s for s in available_strategies
            if self.strategy_stats[s].total_trades < self.min_trades_per_strategy
        ]

        if undertrained_strategies and np.random.random() < 0.4:  # ✅ 40% probabilidad para estrategias con pocos datos
            selected = np.random.choice(undertrained_strategies)
            self.logger.debug(f"🎲 Exploration: selected {selected} (undertrained)")
            return selected

        # Thompson Sampling: sample from posterior distribution
        strategy_samples = {}

        for strategy in available_strategies:
            if strategy not in self.A:
                continue

            try:
                # Calcular parámetros posteriores with error handling
                A_inv = np.linalg.inv(self.A[strategy])
                self.theta[strategy] = A_inv @ self.b[strategy]
            except (np.linalg.LinAlgError, ValueError) as e:
                self.logger.warning(f"⚠️ Matrix operation error for {strategy}: {e}. Skipping.")
                continue
            
            # Sample del posterior (asumiendo ruido gaussiano) - MAS CONSERVADOR
            sigma = A_inv * (self.alpha * 2.0)  # ✅ Varianza más alta para más exploración
            theta_sample = np.random.multivariate_normal(
                self.theta[strategy], 
                sigma
            )
            
            # Calcular reward esperado con el sample
            expected_reward = features @ theta_sample
            strategy_samples[strategy] = expected_reward
        
        if not strategy_samples:
            # Fallback: selección aleatoria
            return np.random.choice(available_strategies)
        
        # Seleccionar estrategia con mayor reward esperado
        best_strategy = max(strategy_samples.keys(), 
                           key=lambda s: strategy_samples[s])
        
        # Log de la selección
        rewards_str = {s: f"{r:.3f}" for s, r in strategy_samples.items()}
        self.logger.debug(f"🧠 ML Selection: {best_strategy} | Rewards: {rewards_str}")
        
        return best_strategy
    
    def add_new_strategy(self, strategy: str):
        """Agregar una nueva estrategia dinámicamente"""
        if strategy not in self.strategies:
            self.strategies.append(strategy)
            self.A[strategy] = np.eye(self.feature_dim) * self.alpha
            self.b[strategy] = np.zeros(self.feature_dim)
            self.theta[strategy] = np.zeros(self.feature_dim)
            self.strategy_stats[strategy] = StrategyPerformance()
            self.logger.info(f"➕ Added new strategy: {strategy}")
    
    def update_model(self, context: TickerContext, strategy: str, reward: float):
        """
        Actualiza el modelo con el resultado del trade
        """
        if strategy not in self.A:
            self.logger.warning(f"Unknown strategy: {strategy} - Adding automatically")
            self.add_new_strategy(strategy)
        
        features = context.to_feature_vector()
        
        # Actualizar matrices del bandit
        self.A[strategy] += np.outer(features, features)
        self.b[strategy] += features * reward
        
        # Actualizar estadísticas
        self.strategy_stats[strategy].update(reward)
        
        self.logger.info(f"📈 Model updated: {strategy} | Reward: {reward:.2f} | "
                        f"WR: {self.strategy_stats[strategy].win_rate:.1%} | "
                        f"Trades: {self.strategy_stats[strategy].total_trades}")
    
    def get_strategy_rankings(self, context: TickerContext) -> List[Tuple[str, float]]:
        """
        Obtiene ranking de estrategias para el contexto actual
        """
        features = context.to_feature_vector()
        rankings = []
        
        for strategy in self.strategies:
            if strategy not in self.theta:
                continue
                
            expected_reward = features @ self.theta[strategy]
            confidence = self.strategy_stats[strategy].total_trades
            
            rankings.append((strategy, expected_reward, confidence))
        
        # Ordenar por reward esperado
        rankings.sort(key=lambda x: x[1], reverse=True)
        
        return [(s, reward) for s, reward, conf in rankings]
    
    def save_model(self, filepath: str):
        """Guarda el modelo entrenado"""
        model_data = {
            'strategies': self.strategies,
            'feature_dim': self.feature_dim,
            'alpha': self.alpha,
            'A': {s: A.tolist() for s, A in self.A.items()},
            'b': {s: b.tolist() for s, b in self.b.items()},
            'theta': {s: theta.tolist() for s, theta in self.theta.items()},
            'strategy_stats': {s: asdict(stats) for s, stats in self.strategy_stats.items()},
            'timestamp': datetime.now().isoformat()
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(model_data, f, indent=2, default=str)
        
        self.logger.info(f"💾 Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Carga modelo previamente entrenado"""
        try:
            with open(filepath, 'r') as f:
                model_data = json.load(f)
            
            self.strategies = model_data['strategies']
            self.feature_dim = model_data['feature_dim'] 
            self.alpha = model_data['alpha']
            
            # Reconstruir matrices numpy
            for strategy in self.strategies:
                if strategy in model_data['A']:
                    self.A[strategy] = np.array(model_data['A'][strategy])
                    self.b[strategy] = np.array(model_data['b'][strategy])
                    self.theta[strategy] = np.array(model_data['theta'][strategy])
            
            # Reconstruir estadísticas
            for s, stats_dict in model_data['strategy_stats'].items():
                if 'last_updated' in stats_dict and stats_dict['last_updated']:
                    stats_dict['last_updated'] = datetime.fromisoformat(stats_dict['last_updated'])
                else:
                    stats_dict['last_updated'] = None
                self.strategy_stats[s] = StrategyPerformance(**stats_dict)
            
            self.logger.info(f"📂 Model loaded from {filepath}")
            
        except Exception as e:
            self.logger.warning(f"Failed to load model: {e}. Starting with fresh model.")
    
    def detect_best_database(self) -> str:
        """
        Detecta automáticamente la mejor base de datos a usar
        Prioridad: trading_data.db > database_quality.db
        """
        # Check production database first
        if os.path.exists(self.primary_db):
            try:
                conn = sqlite3.connect(self.primary_db)
                # Verify it has strategy_outcomes table with data
                result = conn.execute("""
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='table' AND name='strategy_outcomes'
                """).fetchone()
                
                if result[0] > 0:
                    # Check if it has actual data
                    count_result = conn.execute("SELECT COUNT(*) FROM strategy_outcomes").fetchone()
                    if count_result[0] > 0:
                        conn.close()
                        self.logger.info(f"🎯 Using production database: {self.primary_db}")
                        return self.primary_db
                
                conn.close()
            except Exception as e:
                self.logger.warning(f"Error checking {self.primary_db}: {e}")
        
        # Fallback to development database
        if os.path.exists(self.fallback_db):
            try:
                conn = sqlite3.connect(self.fallback_db)
                result = conn.execute("""
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='table' AND name='strategy_outcomes'
                """).fetchone()
                
                if result[0] > 0:
                    count_result = conn.execute("SELECT COUNT(*) FROM strategy_outcomes").fetchone()
                    if count_result[0] > 0:
                        conn.close()
                        self.logger.info(f"📊 Using development database: {self.fallback_db}")
                        return self.fallback_db
                
                conn.close()
            except Exception as e:
                self.logger.warning(f"Error checking {self.fallback_db}: {e}")
        
        # Default fallback
        self.logger.warning("No suitable database found, defaulting to database_quality.db")
        return self.fallback_db
    
    def should_retrain(self, db_path: str) -> bool:
        """
        Determina si debe reentrenarse basado en nuevos datos
        """
        if not self.auto_retrain:
            return False
        
        try:
            conn = sqlite3.connect(db_path)
            current_count = conn.execute("SELECT COUNT(*) FROM strategy_outcomes").fetchone()[0]
            conn.close()
            
            # First time training
            if self.last_training_count == 0:
                self.last_training_count = current_count
                return True
            
            # Check if we have enough new data
            new_data_count = current_count - self.last_training_count
            if new_data_count >= self.retrain_threshold:
                self.logger.info(f"🔄 Auto-retrain triggered: {new_data_count} new outcomes (threshold: {self.retrain_threshold})")
                self.last_training_count = current_count
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking retrain condition: {e}")
            return False
    
    def smart_select_strategy(self, context: ScannerEventContext, 
                             available_strategies: Optional[List[str]] = None) -> str:
        """
        Selección inteligente con auto-retraining y detección automática de DB
        """
        # Detect best database if not set
        if self.current_db is None:
            self.current_db = self.detect_best_database()
        
        # Check if we should retrain
        if self.should_retrain(self.current_db):
            self.logger.info("🧠 Auto-retraining model with new data...")
            self.train_from_database(self.current_db, reset_model=False)  # Incremental training
        
        # Regular strategy selection
        return self.select_strategy(context, available_strategies)
    
    def load_training_data_from_db(self, db_path: str = None) -> List[Tuple[ScannerEventContext, str, float]]:
        """
        Carga datos de entrenamiento con detección automática de DB
        Returns: Lista de (context, strategy, reward) tuples
        """
        if db_path is None:
            db_path = self.detect_best_database()
            self.current_db = db_path
        
        training_data = []
        
        try:
            conn = sqlite3.connect(db_path)
            
            # Check database type and use appropriate query
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ScannerEvents'")
            has_scanner_tables = cursor.fetchone() is not None
            
            if has_scanner_tables:
                # Original query for database_quality.db with scanner data
                query = """
                SELECT 
                    se.id_event, se.ticker as symbol, se.timestamp,
                    sd.precio as entry_price, 1000 as quantity,
                    so.strategy_name, so.success, so.pnl_pct
                FROM ScannerEvents se
                JOIN ScannerData sd ON se.id_event = sd.id_event
                JOIN strategy_outcomes so ON se.id_event = so.id_event
                WHERE sd.precio IS NOT NULL 
                  AND so.pnl_pct IS NOT NULL
                ORDER BY se.timestamp DESC
                """
            else:
                # Query for trading_data.db using real trade data with daily context
                query = """
                SELECT 
                    so.id as id_event,
                    t.symbol,
                    so.timestamp_calculated as timestamp,
                    so.entry_price,
                    t.quantity,
                    so.strategy_name,
                    so.success,
                    so.pnl_pct,
                    COALESCE(ds.win_rate, 50.0) as daily_win_rate,
                    COALESCE(ds.total_pnl, 0.0) as daily_pnl
                FROM strategy_outcomes so
                JOIN trades t ON so.id = t.id
                LEFT JOIN daily_stats ds ON DATE(t.entry_time) = ds.date
                WHERE so.pnl_pct IS NOT NULL
                  AND so.entry_price IS NOT NULL
                  AND t.quantity IS NOT NULL
                ORDER BY so.timestamp_calculated DESC
                """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            self.logger.info(f"📊 Loaded {len(df)} training examples from database")
            
            # Convertir a training data
            for _, row in df.iterrows():
                if has_scanner_tables:
                    # Legacy scanner data
                    event_data = {
                        'id_event': row['id_event'],
                        'ticker': row['symbol'],
                        'timestamp': row['timestamp'],
                        'precio': row['entry_price']
                    }
                    context = ScannerEventContext.from_scanner_data(event_data)
                else:
                    # Real trade data
                    trade_data = {
                        'id_event': row['id_event'],
                        'symbol': row['symbol'],
                        'timestamp': row['timestamp'],
                        'entry_price': row['entry_price'],
                        'quantity': row['quantity'],
                        'daily_win_rate': row.get('daily_win_rate', 50.0),
                        'daily_pnl': row.get('daily_pnl', 0.0)
                    }
                    context = ScannerEventContext.from_trade_data(trade_data)
                
                strategy = row['strategy_name']
                
                # Convertir success y pnl_pct a reward
                # Reward = success (0/1) + bonus por PnL positivo
                reward = float(row['success'])
                if row['pnl_pct'] > 0:
                    reward += min(row['pnl_pct'] * 10, 2.0)  # Bonus limitado
                elif row['pnl_pct'] < 0:
                    reward += max(row['pnl_pct'] * 5, -1.0)  # Penalty limitada
                
                training_data.append((context, strategy, reward))
            
            return training_data
            
        except Exception as e:
            self.logger.error(f"Error loading training data: {e}")
            return []
    
    def train_from_database(self, db_path: str = None, reset_model: bool = True):
        """
        Entrena el modelo usando datos reales con detección automática de DB
        """
        if db_path is None:
            db_path = self.detect_best_database()
            self.current_db = db_path
        
        if reset_model:
            self.logger.info("🔄 Resetting model for fresh training")
            # Reset matrices para fresh training
            for strategy in self.strategies:
                self.A[strategy] = np.eye(self.feature_dim) * self.alpha
                self.b[strategy] = np.zeros(self.feature_dim)
                self.theta[strategy] = np.zeros(self.feature_dim)
                self.strategy_stats[strategy] = StrategyPerformance(strategy)
        
        # Cargar datos de entrenamiento
        training_data = self.load_training_data_from_db(db_path)
        
        if not training_data:
            self.logger.warning("No training data loaded!")
            return
        
        # Entrenar con cada ejemplo
        self.logger.info(f"🧠 Training with {len(training_data)} examples...")
        
        strategy_counts = defaultdict(int)
        total_reward = 0
        
        for context, strategy, reward in training_data:
            # Skip si la estrategia no está en nuestro modelo
            if strategy not in self.strategies:
                continue
                
            # Actualizar modelo
            self.update_model(context, strategy, reward)
            
            strategy_counts[strategy] += 1
            total_reward += reward
        
        # Reporte de entrenamiento
        self.logger.info("📈 Training completed!")
        self.logger.info(f"   Total examples: {len(training_data)}")
        self.logger.info(f"   Average reward: {total_reward/len(training_data):.3f}")
        self.logger.info("   Examples per strategy:")
        
        for strategy in self.strategies:
            count = strategy_counts[strategy]
            stats = self.strategy_stats[strategy]
            self.logger.info(f"     {strategy}: {count} examples, "
                           f"WR: {stats.win_rate:.1%}, "
                           f"Avg reward: {stats.avg_pnl:.3f}")

class TickerProfiler:
    """
    Analiza características de tickers para generar contexto ML
    """
    
    def __init__(self, lookback_bars: int = 100):
        self.lookback_bars = lookback_bars
        self.ticker_data = defaultdict(lambda: deque(maxlen=lookback_bars))
        self.cached_profiles = {}
        self.cache_expiry = timedelta(minutes=5)  # Cache por 5 minutos
        
    def update_ticker_data(self, bar: MarketData):
        """Actualiza datos históricos del ticker"""
        self.ticker_data[bar.symbol].append(bar)
        
        # Invalidar cache si existe
        if bar.symbol in self.cached_profiles:
            del self.cached_profiles[bar.symbol]
    
    def get_ticker_context(self, symbol: str, current_bar: MarketData) -> TickerContext:
        """
        Genera contexto completo del ticker para ML
        """
        # Verificar cache
        cache_key = f"{symbol}_{current_bar.timestamp}"
        if cache_key in self.cached_profiles:
            cached_time, context = self.cached_profiles[cache_key]
            if datetime.now() - cached_time < self.cache_expiry:
                return context
        
        bars = list(self.ticker_data[symbol])
        if len(bars) < 10:
            # Contexto básico para tickers con pocos datos
            context = self._create_basic_context(symbol, current_bar)
        else:
            context = self._create_full_context(symbol, current_bar, bars)
        
        # Cache el resultado
        self.cached_profiles[cache_key] = (datetime.now(), context)
        
        return context
    
    def _create_basic_context(self, symbol: str, bar: MarketData) -> TickerContext:
        """Crea contexto básico para tickers con pocos datos"""
        current_time = datetime.now().time()
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        
        minutes_from_open = max(0, (datetime.combine(datetime.today(), current_time) - 
                                  datetime.combine(datetime.today(), market_open)).total_seconds() / 60)
        
        return TickerContext(
            symbol=symbol,
            current_price=bar.close,
            avg_volume_10=bar.volume,
            avg_volume_50=bar.volume,
            volatility_10=0.05,  # Default volatility
            volatility_50=0.05,
            price_change_1h=0.0,
            price_change_4h=0.0,
            rsi_14=50.0,  # Neutral RSI
            volume_ratio_current=1.0,
            volume_spike_frequency=0.1,
            hour_of_day=current_time.hour + current_time.minute / 60.0,
            minutes_from_open=int(minutes_from_open),
            is_first_hour=minutes_from_open < 60,
            is_last_hour=minutes_from_open > 330,  # Después de 2:30 PM
            market_trend=0.0,  # Neutral
            sector_performance=0.0,
            breakout_success_rate=0.5,
            mean_reversion_tendency=0.5
        )
    
    def _create_full_context(self, symbol: str, current_bar: MarketData, 
                           bars: List[MarketData]) -> TickerContext:
        """Crea contexto completo con análisis técnico"""
        df = self._bars_to_dataframe(bars + [current_bar])
        
        # Cálculos técnicos básicos
        current_price = current_bar.close
        avg_volume_10 = df['volume'].tail(10).mean()
        avg_volume_50 = df['volume'].mean()
        
        # Volatilidad
        returns = df['close'].pct_change().dropna()
        volatility_10 = returns.tail(10).std() if len(returns) >= 10 else 0.05
        volatility_50 = returns.std() if len(returns) >= 20 else 0.05
        
        # Cambios de precio
        price_change_1h = self._calculate_price_change(df, periods=12)  # 12 periods = 1 hour (5min bars)
        price_change_4h = self._calculate_price_change(df, periods=48)  # 48 periods = 4 hours
        
        # RSI
        rsi_14 = self._calculate_rsi(df['close'], 14)
        
        # Análisis de volumen
        volume_ratio = current_bar.volume / avg_volume_50 if avg_volume_50 > 0 else 1.0
        volume_spike_frequency = self._calculate_volume_spike_frequency(df)
        
        # Contexto temporal
        current_time = datetime.now().time()
        hour_of_day = current_time.hour + current_time.minute / 60.0
        minutes_from_open = max(0, (datetime.combine(datetime.today(), current_time) - 
                                  datetime.combine(datetime.today(), datetime.strptime("09:30", "%H:%M").time())).total_seconds() / 60)
        
        # Patrones históricos
        breakout_success = self._calculate_breakout_success_rate(df)
        mean_reversion = self._calculate_mean_reversion_tendency(df)
        
        return TickerContext(
            symbol=symbol,
            current_price=current_price,
            avg_volume_10=avg_volume_10,
            avg_volume_50=avg_volume_50,
            volatility_10=volatility_10,
            volatility_50=volatility_50,
            price_change_1h=price_change_1h,
            price_change_4h=price_change_4h,
            rsi_14=rsi_14,
            volume_ratio_current=volume_ratio,
            volume_spike_frequency=volume_spike_frequency,
            hour_of_day=hour_of_day,
            minutes_from_open=int(minutes_from_open),
            is_first_hour=minutes_from_open < 60,
            is_last_hour=minutes_from_open > 330,
            market_trend=0.0,  # TODO: Implement market sentiment
            sector_performance=0.0,  # TODO: Implement sector tracking
            breakout_success_rate=breakout_success,
            mean_reversion_tendency=mean_reversion
        )
    
    def _bars_to_dataframe(self, bars: List[MarketData]) -> pd.DataFrame:
        """Convierte bars a DataFrame"""
        data = []
        for bar in bars:
            data.append({
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    
    def _calculate_price_change(self, df: pd.DataFrame, periods: int) -> float:
        """Calcula cambio de precio en N períodos"""
        if len(df) <= periods:
            return 0.0
        current_price = df['close'].iloc[-1]
        past_price = df['close'].iloc[-periods-1]
        return (current_price - past_price) / past_price
    
    def _calculate_rsi(self, prices: pd.Series, window: int) -> float:
        """Calcula RSI"""
        if len(prices) < window + 1:
            return 50.0
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
    
    def _calculate_volume_spike_frequency(self, df: pd.DataFrame) -> float:
        """Calcula frecuencia de picos de volumen"""
        if len(df) < 20:
            return 0.1
        
        avg_volume = df['volume'].mean()
        spikes = df['volume'] > (avg_volume * 2.0)  # Volumen > 2x promedio
        return spikes.sum() / len(df)
    
    def _calculate_breakout_success_rate(self, df: pd.DataFrame) -> float:
        """Calcula tasa de éxito de breakouts"""
        if len(df) < 30:
            return 0.5
        
        # Identificar breakouts (precio rompe máximo de últimos 20 períodos)
        df_copy = df.copy()
        df_copy['resistance'] = df_copy['high'].rolling(window=20).max().shift(1)
        df_copy['breakout'] = df_copy['high'] > df_copy['resistance']
        
        breakouts = df_copy[df_copy['breakout']]
        if len(breakouts) == 0:
            return 0.5
        
        # Contar éxitos (precio continúa subiendo)
        success_count = 0
        for idx in breakouts.index:
            try:
                breakout_price = df_copy.loc[idx, 'high']
                future_data = df_copy.loc[idx:].head(10)[1:]  # Próximos 9 bars
                if len(future_data) >= 3:
                    max_future = future_data['high'].max()
                    if max_future > breakout_price * 1.01:  # Al menos 1% más alto
                        success_count += 1
            except:
                continue
        
        return success_count / len(breakouts)
    
    def _calculate_mean_reversion_tendency(self, df: pd.DataFrame) -> float:
        """Calcula tendencia a mean reversion"""
        if len(df) < 40:
            return 0.5
        
        # Calcular desviaciones de SMA
        df_copy = df.copy()
        df_copy['sma_20'] = df_copy['close'].rolling(window=20).mean()
        df_copy['deviation'] = (df_copy['close'] - df_copy['sma_20']) / df_copy['sma_20']
        
        # Contar casos de reversión
        reversion_count = 0
        total_cases = 0
        
        for i in range(20, len(df_copy) - 10):
            if abs(df_copy.iloc[i]['deviation']) > 0.05:  # Desviación > 5%
                total_cases += 1
                # Ver si revierte en próximos 10 bars
                future_deviation = abs(df_copy.iloc[i+10]['deviation']) if i+10 < len(df_copy) else abs(df_copy.iloc[-1]['deviation'])
                if future_deviation < abs(df_copy.iloc[i]['deviation']):
                    reversion_count += 1
        
        return reversion_count / total_cases if total_cases > 0 else 0.5

    def _secure_fallback_strategy_selection(self, available_strategies: List[str], features: np.ndarray) -> str:
        """
        Secure fallback strategy selection that respects strategy validations
        Used when feature dimension mismatch occurs to prevent bypassing validations
        """
        try:
            # Priority-based fallback with validation awareness
            strategy_priorities = {
                # Conservative strategies with strong validations (higher priority)
                'macdv_smallcaps': 10,  # Strong volume + MACD validation
                'volume_breakout': 8,   # Volume validation
                'orb': 7,              # Time-based validation
                # More aggressive strategies (lower priority for fallback)
                'gap_go': 5,
                'daily_plays': 4,
                'explosive_volume': 3,
                'first_day_bounce': 2,
                'catalyst_momentum': 1
            }

            # Filter available strategies and sort by priority
            prioritized_strategies = []
            for strategy in available_strategies:
                priority = strategy_priorities.get(strategy, 0)
                if priority > 0:
                    prioritized_strategies.append((strategy, priority))

            # Sort by priority (highest first)
            prioritized_strategies.sort(key=lambda x: x[1], reverse=True)

            if prioritized_strategies:
                selected_strategy = prioritized_strategies[0][0]
                self.logger.info(f"🛡️ SECURE FALLBACK: Selected {selected_strategy} (priority: {prioritized_strategies[0][1]})")
                return selected_strategy

            # Final fallback to most conservative strategy
            conservative_fallback = 'orb' if 'orb' in available_strategies else (
                available_strategies[0] if available_strategies else 'orb'
            )

            self.logger.warning(f"🛡️ FINAL FALLBACK: Using conservative strategy {conservative_fallback}")
            return conservative_fallback

        except Exception as e:
            self.logger.error(f"Error in secure fallback selection: {e}")
            # Emergency fallback
            return available_strategies[0] if available_strategies else 'orb'

# Factory functions
def create_ml_strategy_selector(strategies: List[str],
                               model_path: str = "data/ml_models/strategy_selector.json",
                               auto_retrain: bool = True) -> ContextualBandit:
    """Crea y configura el selector ML de estrategias con auto-detected feature dimensions"""
    # Auto-detect feature dimension from TickerContext
    # Create a dummy context to get the feature dimension
    try:
        dummy_context = TickerContext(
            symbol='DUMMY',
            current_price=10.0,
            avg_volume_10=1000.0,
            avg_volume_50=1000.0,
            volatility_10=0.02,
            volatility_50=0.02,
            price_change_1h=0.0,
            price_change_4h=0.0,
            rsi_14=50.0,
            volume_ratio_current=1.0,
            volume_spike_frequency=0.0,
            hour_of_day=10.0,
            minutes_from_open=30,
            is_first_hour=False,
            is_last_hour=False,
            market_trend=0.0,
            sector_performance=0.0,
            breakout_success_rate=0.5,
            mean_reversion_tendency=0.5
        )
        feature_dim = len(dummy_context.to_feature_vector())
        logger.info(f"🔍 Auto-detected feature dimension: {feature_dim}")
    except Exception as e:
        # Fallback to 18 (known TickerContext feature count)
        feature_dim = 18
        logger.warning(f"⚠️ Failed to auto-detect features, using fallback dimension {feature_dim}: {e}")

    bandit = ContextualBandit(strategies, feature_dim=feature_dim, auto_retrain=auto_retrain)
    
    # Intentar cargar modelo existente
    if os.path.exists(model_path):
        bandit.load_model(model_path)
        bandit.logger.info(f"✅ Loaded model with {feature_dim} features")
    else:
        # Auto-train si no hay modelo
        bandit.logger.info("🚀 No existing model found, auto-training with trend features...")
        bandit.train_from_database()  # Will use trading_data.db as primary
        bandit.save_model(model_path)
    
    return bandit

def create_ticker_profiler() -> TickerProfiler:
    """Crea el profiler de tickers"""
    return TickerProfiler()

if __name__ == "__main__":
    # Test básico
    print("🧪 ML Strategy Selector Test")
    print("=" * 50)
    
    strategies = ['macdv_smallcaps', 'gap_go', 'orb', 'vcp', 'daily_plays']
    bandit = create_ml_strategy_selector(strategies)
    profiler = create_ticker_profiler()
    
    print(f"Strategies: {strategies}")
    print(f"Feature dimension: {bandit.feature_dim}")
    print(f"Exploration rate: {bandit.exploration_rate}")
    print("=" * 50)
    print("✅ ML Strategy Selector ready!")