#!/usr/bin/env python3
"""
Trend Feature Calculator
Calculates trend-based features from existing trade data for ML enhancement
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrendFeatureCalculator:
    """Calculate trend features from existing trade data"""
    
    def __init__(self, db_path: str = 'trading_data.db'):
        self.db_path = db_path
        
    def calculate_symbol_trend_features(self, symbol: str, entry_time: str, entry_price: float) -> Dict[str, float]:
        """
        Calculate trend features for a specific symbol at a specific time
        
        Args:
            symbol: Stock symbol (e.g., 'DSY')
            entry_time: Entry timestamp for the trade
            entry_price: Entry price for the trade
            
        Returns:
            Dict with calculated trend features
        """
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get historical trades for this symbol before the entry time
            query = """
                SELECT entry_price, entry_time, pnl, quantity 
                FROM trades 
                WHERE symbol = ? 
                  AND entry_time < ?
                  AND entry_price IS NOT NULL
                ORDER BY entry_time DESC
                LIMIT 20
            """
            
            df = pd.read_sql_query(query, conn, params=(symbol, entry_time))
            conn.close()
            
            if len(df) < 3:  # Need at least 3 historical points
                return self._default_features(entry_price)
            
            # Calculate trend features
            features = {}
            
            # Recent price statistics
            recent_prices = df['entry_price'].head(10).values
            features['recent_high_5d'] = float(np.max(recent_prices[:5]) if len(recent_prices) >= 5 else entry_price)
            features['recent_low_5d'] = float(np.min(recent_prices[:5]) if len(recent_prices) >= 5 else entry_price)
            features['recent_avg_price'] = float(np.mean(recent_prices))
            
            # Price momentum (current price vs recent average)
            features['price_momentum'] = float(entry_price / features['recent_avg_price'])
            
            # Relative position in recent range
            price_range = features['recent_high_5d'] - features['recent_low_5d']
            if price_range > 0:
                features['relative_position'] = float((entry_price - features['recent_low_5d']) / price_range)
            else:
                features['relative_position'] = 0.5
                
            # Symbol strength (recent performance)
            if 'pnl' in df.columns:
                recent_pnl = df['pnl'].head(5).dropna()
                if len(recent_pnl) > 0:
                    features['symbol_strength'] = float(recent_pnl.mean())
                else:
                    features['symbol_strength'] = 0.0
            else:
                features['symbol_strength'] = 0.0
            
            # Volume trend (simplified)
            features['volume_trend'] = 1.0  # Default, will improve with actual volume data
            
            # Market context (simplified classification)
            features['market_context'] = self._classify_market_context(features['price_momentum'])
            
            return features
            
        except Exception as e:
            logger.error(f"Error calculating trend features for {symbol}: {e}")
            return self._default_features(entry_price)
    
    def _default_features(self, entry_price: float) -> Dict[str, float]:
        """Default feature values when insufficient data"""
        return {
            'recent_high_5d': entry_price,
            'recent_low_5d': entry_price,
            'recent_avg_price': entry_price,
            'price_momentum': 1.0,
            'volume_trend': 1.0,
            'relative_position': 0.5,
            'symbol_strength': 0.0,
            'market_context': 'NEUTRAL'
        }
    
    def _classify_market_context(self, momentum: float) -> str:
        """Classify market context based on momentum"""
        if momentum >= 1.1:
            return 'BULLISH'
        elif momentum <= 0.9:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def backfill_all_trades(self):
        """Backfill all existing trades with trend features"""
        logger.info("🔄 Starting backfill of trend features...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all trades that need trend features
        trades = cursor.execute("""
            SELECT id, symbol, entry_time, entry_price 
            FROM trades 
            WHERE entry_price IS NOT NULL
            ORDER BY entry_time ASC
        """).fetchall()
        
        logger.info(f"📊 Processing {len(trades)} trades...")
        
        updated_count = 0
        for trade_id, symbol, entry_time, entry_price in trades:
            try:
                # Calculate trend features for this trade
                features = self.calculate_symbol_trend_features(symbol, entry_time, entry_price)
                
                # Update the trade record
                cursor.execute("""
                    UPDATE trades SET
                        recent_high_5d = ?,
                        recent_low_5d = ?,
                        recent_avg_price = ?,
                        price_momentum = ?,
                        volume_trend = ?,
                        relative_position = ?,
                        symbol_strength = ?,
                        market_context = ?
                    WHERE id = ?
                """, (
                    features['recent_high_5d'],
                    features['recent_low_5d'], 
                    features['recent_avg_price'],
                    features['price_momentum'],
                    features['volume_trend'],
                    features['relative_position'],
                    features['symbol_strength'],
                    features['market_context'],
                    trade_id
                ))
                
                updated_count += 1
                
                if updated_count % 10 == 0:
                    logger.info(f"   ✅ Processed {updated_count}/{len(trades)} trades...")
                    
            except Exception as e:
                logger.error(f"Error processing trade {trade_id}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Backfill completed! Updated {updated_count} trades with trend features")
        return updated_count

    def test_features_for_dsy(self):
        """Test the feature calculation specifically for DSY trades"""
        logger.info("🧪 Testing trend features for DSY trades...")
        
        conn = sqlite3.connect(self.db_path)
        
        # Get DSY trades to see the calculated features
        dsy_trades = pd.read_sql_query("""
            SELECT entry_time, entry_price, price_momentum, relative_position, 
                   symbol_strength, market_context
            FROM trades 
            WHERE symbol = 'DSY' 
            ORDER BY entry_time ASC
        """, conn)
        
        conn.close()
        
        if len(dsy_trades) > 0:
            logger.info("📊 DSY trades with trend features:")
            for _, trade in dsy_trades.iterrows():
                logger.info(f"   Price: ${trade['entry_price']:.2f} | "
                          f"Momentum: {trade['price_momentum']:.3f} | "
                          f"Position: {trade['relative_position']:.3f} | "
                          f"Context: {trade['market_context']}")
        else:
            logger.warning("No DSY trades found in database")
        
        return dsy_trades

if __name__ == "__main__":
    calculator = TrendFeatureCalculator()
    
    # Test single symbol calculation
    print("🧪 Testing single calculation...")
    test_features = calculator.calculate_symbol_trend_features(
        symbol='DSY',
        entry_time='2025-09-09 21:28:02',
        entry_price=3.03
    )
    print(f"Test features: {test_features}")
    
    # Backfill all trades
    print("\n🔄 Starting full backfill...")
    updated = calculator.backfill_all_trades()
    print(f"✅ Updated {updated} trades")
    
    # Test DSY specifically
    print("\n🧪 Testing DSY results...")
    calculator.test_features_for_dsy()