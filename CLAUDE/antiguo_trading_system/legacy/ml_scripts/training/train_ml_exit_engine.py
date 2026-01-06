#!/usr/bin/env python3
"""
ML Exit Engine Trainer - Entrena el motor de salidas usando database.db
========================================================================

Usa la tabla OHLCData para entrenar modelos de exit timing optimization.
Cada evento (id_event) representa un día de trading independiente.
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, mean_absolute_error
import joblib
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLExitTrainer:
    """
    Entrenador del ML Exit Engine usando datos históricos reales
    """
    
    def __init__(self, database_path: str = "database_quality.db", models_dir: str = "core/models/exit_models"):
        self.database_path = database_path
        self.models_dir = models_dir
        self.logger = logger
        
        # Ensure models directory exists
        os.makedirs(models_dir, exist_ok=True)
        
        # Initialize components
        self.exit_classifier = None
        self.profit_regressor = None
        self.scaler = StandardScaler()
        
        self.logger.info(f"🎯 ML Exit Trainer initialized")
        self.logger.info(f"   Database: {database_path}")
        self.logger.info(f"   Models dir: {models_dir}")
    
    def load_training_data(self, min_bars: int = 100, max_events: Optional[int] = None) -> pd.DataFrame:
        """
        Load and preprocess training data from database.db
        """
        self.logger.info("📊 Loading training data from database.db...")
        
        conn = sqlite3.connect(self.database_path)
        
        # Query to get events with OHLC data
        query = """
        SELECT 
            se.id_event,
            se.ticker,
            se.timestamp as event_date,
            o.date as bar_time,
            o.open,
            o.high,
            o.low,
            o.close,
            o.volume,
            ROW_NUMBER() OVER (PARTITION BY se.id_event ORDER BY o.date) as bar_number
        FROM ScannerEvents se
        JOIN OHLCData o ON se.id_event = o.id_event
        WHERE se.id_event IN (
            SELECT id_event 
            FROM OHLCData 
            GROUP BY id_event 
            HAVING COUNT(*) >= ?
        )
        ORDER BY se.id_event, o.date
        """
        
        if max_events:
            query += f" LIMIT {max_events * 1000}"  # Rough limit
        
        df = pd.read_sql_query(query, conn, params=[min_bars])
        conn.close()
        
        self.logger.info(f"✅ Loaded {len(df):,} bars from {df['id_event'].nunique():,} events")
        self.logger.info(f"   Tickers: {df['ticker'].nunique():,} unique symbols")
        self.logger.info(f"   Date range: {df['bar_time'].min()} to {df['bar_time'].max()}")
        
        return df
    
    def create_exit_features(self, event_data: pd.DataFrame) -> pd.DataFrame:
        """
        Create features for each potential exit point in an event
        """
        features_list = []
        
        # Ensure data is sorted by time
        event_data = event_data.sort_values('bar_number')
        
        id_event = event_data['id_event'].iloc[0]
        ticker = event_data['ticker'].iloc[0]
        
        # Calculate technical indicators
        event_data['returns'] = event_data['close'].pct_change()
        event_data['volume_sma'] = event_data['volume'].rolling(10, min_periods=1).mean()
        event_data['volume_ratio'] = event_data['volume'] / event_data['volume_sma']
        
        # RSI calculation
        delta = event_data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
        rs = gain / loss
        event_data['rsi'] = 100 - (100 / (1 + rs))
        
        # VWAP calculation
        event_data['vwap'] = (event_data['close'] * event_data['volume']).cumsum() / event_data['volume'].cumsum()
        event_data['price_vs_vwap'] = event_data['close'] / event_data['vwap']
        
        # For each potential exit point (after bar 30, before last 10 bars)
        min_entry_bar = 30  # Need some history
        max_exit_bar = len(event_data) - 10  # Leave some future data to calculate outcomes
        
        for exit_idx in range(min_entry_bar, max_exit_bar, 5):  # Every 5 minutes
            try:
                # Simulate entry at bar 10-29 (random entry point)
                entry_idx = np.random.randint(10, min(30, exit_idx - 10))
                entry_price = event_data.iloc[entry_idx]['close']
                entry_time = event_data.iloc[entry_idx]['bar_number']
                
                # Current state at exit decision point
                current_bar = event_data.iloc[exit_idx]
                current_price = current_bar['close']
                
                # Calculate features
                time_in_position = exit_idx - entry_idx  # minutes
                current_pnl_pct = (current_price - entry_price) / entry_price
                
                # Market features at decision point
                current_volume_ratio = current_bar['volume_ratio']
                current_rsi = current_bar['rsi']
                price_vs_vwap = current_bar['price_vs_vwap']
                
                # Time-based features
                time_of_day = (exit_idx / len(event_data))  # Normalized position in day
                
                # Momentum features (last 5 bars)
                recent_returns = event_data.iloc[max(0, exit_idx-5):exit_idx+1]['returns']
                price_momentum = recent_returns.sum() if len(recent_returns) > 0 else 0
                
                volume_trend = 0
                if exit_idx >= 5:
                    recent_volumes = event_data.iloc[exit_idx-4:exit_idx+1]['volume_ratio']
                    volume_trend = recent_volumes.diff().sum()
                
                # Calculate future outcomes for labels
                # Look 10, 30, 60 minutes ahead
                future_outcomes = {}
                for horizon in [10, 30, 60]:
                    future_idx = min(exit_idx + horizon, len(event_data) - 1)
                    future_price = event_data.iloc[future_idx]['close']
                    future_return = (future_price - current_price) / current_price
                    future_outcomes[f'return_{horizon}min'] = future_return
                
                # Determine optimal exit decision (label)
                # Exit if current profit > 0 and future returns are negative
                # Or if current loss is small but future loss is large
                should_exit = self._should_exit_label(current_pnl_pct, future_outcomes)
                
                # Expected value if holding vs exiting
                expected_value_hold = max(future_outcomes.values())  # Best future outcome
                expected_value_exit = current_pnl_pct  # Current P&L
                
                features = {
                    'id_event': id_event,
                    'ticker': ticker,
                    'entry_bar': entry_time,
                    'exit_bar': exit_idx,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'current_pnl_pct': current_pnl_pct,
                    'time_in_position_minutes': time_in_position,
                    'current_volume_ratio': current_volume_ratio,
                    'rsi': current_rsi,
                    'price_vs_vwap': price_vs_vwap,
                    'time_of_day': time_of_day,
                    'price_momentum': price_momentum,
                    'volume_trend': volume_trend,
                    
                    # Labels
                    'should_exit': should_exit,
                    'expected_value_exit': expected_value_exit,
                    'expected_value_hold': expected_value_hold,
                    **future_outcomes
                }
                
                features_list.append(features)
                
            except Exception as e:
                self.logger.warning(f"Error creating features for event {id_event} bar {exit_idx}: {e}")
                continue
        
        if not features_list:
            self.logger.warning(f"No features created for event {id_event}")
            return pd.DataFrame()
        
        return pd.DataFrame(features_list)
    
    def _should_exit_label(self, current_pnl: float, future_outcomes: Dict[str, float]) -> bool:
        """
        Determine if exiting now is optimal based on current and future outcomes
        """
        # Simple heuristic for labeling:
        # Exit if:
        # 1. We have profit > 2% and best future return < current profit
        # 2. We have small loss < 3% but future losses are > 5%
        # 3. We have been holding for a while and profit is stagnating
        
        best_future = max(future_outcomes.values())
        worst_future = min(future_outcomes.values())
        
        if current_pnl > 0.02:  # 2%+ profit
            if best_future < current_pnl * 0.8:  # Future best is much worse
                return True
        
        if current_pnl > -0.03:  # Small loss
            if worst_future < -0.05:  # Future could be much worse
                return True
        
        if current_pnl > 0.01 and best_future < current_pnl * 0.9:  # Profit stagnation
            return True
        
        return False
    
    def prepare_training_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare features and labels for training
        """
        self.logger.info("🔧 Preparing training data...")
        
        # Feature columns
        feature_cols = [
            'current_pnl_pct', 'time_in_position_minutes', 'current_volume_ratio',
            'rsi', 'price_vs_vwap', 'time_of_day', 'price_momentum', 'volume_trend'
        ]
        
        # Remove rows with NaN values
        df_clean = df.dropna(subset=feature_cols + ['should_exit', 'expected_value_hold'])
        
        X = df_clean[feature_cols].values
        y_classification = df_clean['should_exit'].values
        y_regression = df_clean['expected_value_hold'].values
        
        self.logger.info(f"✅ Training data prepared:")
        self.logger.info(f"   Samples: {len(X):,}")
        self.logger.info(f"   Features: {len(feature_cols)}")
        self.logger.info(f"   Exit decisions: {y_classification.sum():,} exits out of {len(y_classification):,} ({y_classification.mean():.1%})")
        
        return X, y_classification, y_regression
    
    def train_models(self, X: np.ndarray, y_classification: np.ndarray, y_regression: np.ndarray) -> Dict[str, float]:
        """
        Train both classification and regression models
        """
        self.logger.info("🤖 Training ML models...")
        
        # Split data
        X_train, X_test, y_class_train, y_class_test, y_reg_train, y_reg_test = train_test_split(
            X, y_classification, y_regression, test_size=0.2, random_state=42, stratify=y_classification
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # ✅ MODELOS ULTRA-CONSERVADORES para evitar overfitting con datos limitados
        
        # Classification model: Logistic Regression (simple y robusto)
        self.exit_classifier = LogisticRegression(
            C=0.1,                    # ✅ Regularización fuerte (L2)
            max_iter=1000,
            random_state=42,
            class_weight='balanced'   # ✅ Balance automático de clases
        )
        
        # Validación cruzada antes de entrenar
        cv_scores_class = cross_val_score(self.exit_classifier, X_train_scaled, y_class_train, cv=3)
        self.logger.info(f"📊 Classification CV scores: {cv_scores_class.mean():.3f} ± {cv_scores_class.std():.3f}")
        
        self.exit_classifier.fit(X_train_scaled, y_class_train)
        
        # Regression model: Ridge (simple y robusto)
        self.profit_regressor = Ridge(
            alpha=10.0,              # ✅ Regularización extrema
            random_state=42
        )
        
        # Validación cruzada antes de entrenar
        cv_scores_reg = cross_val_score(self.profit_regressor, X_train_scaled, y_reg_train, cv=3, scoring='r2')
        self.logger.info(f"📊 Regression CV scores: {cv_scores_reg.mean():.3f} ± {cv_scores_reg.std():.3f}")
        
        self.profit_regressor.fit(X_train_scaled, y_reg_train)
        
        # Evaluate models
        class_pred = self.exit_classifier.predict(X_test_scaled)
        class_accuracy = accuracy_score(y_class_test, class_pred)
        
        reg_pred = self.profit_regressor.predict(X_test_scaled)
        reg_mae = mean_absolute_error(y_reg_test, reg_pred)
        
        # Cross-validation scores
        cv_class_scores = cross_val_score(self.exit_classifier, X_train_scaled, y_class_train, cv=5)
        cv_reg_scores = cross_val_score(self.profit_regressor, X_train_scaled, y_reg_train, cv=5, scoring='neg_mean_absolute_error')
        
        results = {
            'classification_accuracy': class_accuracy,
            'classification_cv_mean': cv_class_scores.mean(),
            'regression_mae': reg_mae,
            'regression_cv_mean': -cv_reg_scores.mean(),  # Negative because of neg_mean_absolute_error
        }
        
        self.logger.info(f"✅ Model training completed:")
        self.logger.info(f"   Classification accuracy: {class_accuracy:.3f}")
        self.logger.info(f"   Classification CV: {cv_class_scores.mean():.3f} ± {cv_class_scores.std():.3f}")
        self.logger.info(f"   Regression MAE: {reg_mae:.4f}")
        self.logger.info(f"   Regression CV: {-cv_reg_scores.mean():.4f} ± {cv_reg_scores.std():.4f}")
        
        # Feature importance
        if hasattr(self.exit_classifier, 'feature_importances_'):
            feature_names = ['pnl_pct', 'time_in_pos', 'vol_ratio', 'rsi', 'price_vwap', 'time_day', 'momentum', 'vol_trend']
            importance = self.exit_classifier.feature_importances_
            self.logger.info("🎯 Feature importance (classification):")
            for name, imp in sorted(zip(feature_names, importance), key=lambda x: x[1], reverse=True):
                self.logger.info(f"   {name}: {imp:.3f}")
        
        return results
    
    def save_models(self, strategy: str = "default") -> None:
        """
        Save trained models to disk
        """
        self.logger.info(f"💾 Saving models for strategy: {strategy}")
        
        strategy_dir = os.path.join(self.models_dir, strategy)
        os.makedirs(strategy_dir, exist_ok=True)
        
        # Save models
        if self.exit_classifier:
            joblib.dump(self.exit_classifier, os.path.join(strategy_dir, 'exit_classifier.pkl'))
        
        if self.profit_regressor:
            joblib.dump(self.profit_regressor, os.path.join(strategy_dir, 'profit_regressor.pkl'))
        
        # Save scaler
        joblib.dump(self.scaler, os.path.join(strategy_dir, 'scaler.pkl'))
        
        # Save metadata
        metadata = {
            'trained_at': datetime.now().isoformat(),
            'strategy': strategy,
            'feature_names': ['current_pnl_pct', 'time_in_position_minutes', 'current_volume_ratio',
                            'rsi', 'price_vs_vwap', 'time_of_day', 'price_momentum', 'volume_trend']
        }
        
        import json
        with open(os.path.join(strategy_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"✅ Models saved to {strategy_dir}")
    
    def run_full_training(self, max_events: int = 500, min_bars: int = 200) -> Dict[str, float]:
        """
        Run complete training pipeline
        """
        self.logger.info("🚀 Starting full ML Exit Engine training...")
        self.logger.info(f"   Max events: {max_events}")
        self.logger.info(f"   Min bars per event: {min_bars}")
        
        # Step 1: Load data
        df_raw = self.load_training_data(min_bars=min_bars, max_events=max_events)
        
        if df_raw.empty:
            raise ValueError("No training data loaded")
        
        # Step 2: Create features for each event
        all_features = []
        events = df_raw['id_event'].unique()
        
        self.logger.info(f"🔄 Processing {len(events)} events...")
        
        for i, event_id in enumerate(events[:max_events]):
            if i % 50 == 0:
                self.logger.info(f"   Processing event {i+1}/{len(events[:max_events])}: {event_id}")
            
            event_data = df_raw[df_raw['id_event'] == event_id].copy()
            event_features = self.create_exit_features(event_data)
            
            if not event_features.empty:
                all_features.append(event_features)
        
        if not all_features:
            raise ValueError("No features created from events")
        
        # Combine all features
        df_features = pd.concat(all_features, ignore_index=True)
        self.logger.info(f"✅ Created {len(df_features):,} training samples")
        
        # Step 3: Prepare training data
        X, y_class, y_reg = self.prepare_training_data(df_features)
        
        # Step 4: Train models
        results = self.train_models(X, y_class, y_reg)
        
        # Step 5: Save models
        self.save_models("smallcap_exit")
        
        self.logger.info("🎉 ML Exit Engine training completed!")
        return results

def main():
    """Main training script"""
    try:
        trainer = MLExitTrainer()
        results = trainer.run_full_training(max_events=300, min_bars=150)
        
        print("\n" + "="*50)
        print("🎯 TRAINING RESULTS SUMMARY")
        print("="*50)
        for key, value in results.items():
            print(f"{key:25}: {value:.4f}")
        print("="*50)
        
        print("\n✅ Training completed successfully!")
        print("🔄 Models saved and ready for use in MLExitEngine")
        
    except Exception as e:
        logger.error(f"❌ Training failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()