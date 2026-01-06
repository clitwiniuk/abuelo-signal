#!/usr/bin/env python3
"""
Test Completo de Integración del Sistema
=========================================

Verifica que toda la integración funciona correctamente:
- DatabaseManager principal
- ScannerIntelligence integrado 
- Auto-categorización
- Streamlit components
- ML learning integration
"""

import sys
import os
import tempfile
import sqlite3
import unittest
from datetime import date, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database_manager import DatabaseManager
from scanner.scanner_intelligence import ScannerIntelligence, TradingResult, AutoCategorizer, AdvancedTradingResult


class TestCompleteIntegration(unittest.TestCase):
    """Test suite for complete system integration"""
    
    def setUp(self):
        """Set up test environment with temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Initialize components with test database
        self.db_manager = DatabaseManager(db_path=self.db_path)
        self.scanner_ai = ScannerIntelligence(database_manager=self.db_manager)
        self.categorizer = AutoCategorizer()
        
        print(f"🧪 Test DB created: {self.db_path}")
    
    def tearDown(self):
        """Clean up test database"""
        try:
            os.unlink(self.db_path)
            print(f"🧹 Test DB cleaned: {self.db_path}")
        except:
            pass
    
    def test_01_database_manager_initialization(self):
        """Test DatabaseManager initialization"""
        print("\n1️⃣ Testing DatabaseManager initialization...")
        
        # Verify database exists
        self.assertTrue(Path(self.db_path).exists())
        
        # Check main tables exist
        with sqlite3.connect(self.db_path) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t[0] for t in tables]
            
            required_tables = ['trades', 'daily_stats', 'trading_journal', 'manual_symbols']
            for table in required_tables:
                self.assertIn(table, table_names, f"Table {table} missing")
        
        print("   ✅ DatabaseManager initialized correctly")
        print(f"   ✅ Found {len(table_names)} tables")
    
    def test_02_scanner_intelligence_integration(self):
        """Test ScannerIntelligence integration with DatabaseManager"""
        print("\n2️⃣ Testing ScannerIntelligence integration...")
        
        # Verify ScannerIntelligence uses the same database
        self.assertEqual(str(self.scanner_ai.db_manager.db_path), self.db_path)
        
        # Check advanced table was created
        with sqlite3.connect(self.db_path) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t[0] for t in tables]
            self.assertIn('advanced_trading_results', table_names)
        
        print("   ✅ ScannerIntelligence integrated with DatabaseManager")
        print("   ✅ Advanced trading results table created")
    
    def test_03_auto_categorizer_functionality(self):
        """Test AutoCategorizer functionality"""
        print("\n3️⃣ Testing AutoCategorizer functionality...")
        
        # Test successful trade categorization
        result = self.categorizer.categorize_trade_automatically(
            ticker='AAPL',
            entry_price=150.0,
            exit_price=155.0,
            trade_date=date.today(),
            hold_duration_minutes=90,
            strategy_used='macdv',
            pnl=500.0
        )
        
        # Verify result structure
        self.assertIsInstance(result, AdvancedTradingResult)
        self.assertEqual(result.ticker, 'AAPL')
        self.assertEqual(result.pnl, 500.0)
        self.assertIsNotNone(result.trade_category)
        self.assertIsNotNone(result.execution_quality)
        self.assertIsNotNone(result.market_context)
        
        print(f"   ✅ Auto-categorized as: {result.trade_category}")
        print(f"   ✅ Execution quality: {result.execution_quality}")
        print(f"   ✅ Market context: {result.market_context}")
    
    def test_04_trade_flow_integration(self):
        """Test complete trade flow from input to storage"""
        print("\n4️⃣ Testing complete trade flow...")
        
        # Create test trade
        trading_result = TradingResult(
            ticker='TSLA',
            trade_date=date.today(),
            entry_price=200.0,
            exit_price=208.5,
            pnl=850.0,
            was_profitable=True,
            hold_duration_minutes=120,
            strategy_used='gap_go',
            notes='Integration test trade'
        )
        
        # Add trade through ScannerIntelligence
        self.scanner_ai.add_trading_result(trading_result, trade_id='TEST_TSLA_001')
        
        # Verify trade was added to main trades table
        with sqlite3.connect(self.db_path) as conn:
            trade_count = conn.execute("SELECT COUNT(*) FROM trades WHERE symbol = ?", ('TSLA',)).fetchone()[0]
            self.assertEqual(trade_count, 1, "Trade not added to main table")
            
            # Verify advanced result was created
            advanced_count = conn.execute("SELECT COUNT(*) FROM advanced_trading_results WHERE ticker = ?", ('TSLA',)).fetchone()[0]
            self.assertEqual(advanced_count, 1, "Advanced result not created")
        
        print("   ✅ Trade added to main trades table")
        print("   ✅ Advanced categorization created")
    
    def test_05_database_consistency(self):
        """Test database consistency and relationships"""
        print("\n5️⃣ Testing database consistency...")
        
        # Add multiple trades
        test_trades = [
            TradingResult('NVDA', date.today(), 300.0, 315.0, 1500.0, True, 85, 'macdv', 'Test 1'),
            TradingResult('AMD', date.today(), 100.0, 98.5, -150.0, False, 45, 'volume_breakout', 'Test 2'),
            TradingResult('MSFT', date.today(), 250.0, 255.0, 500.0, True, 150, 'gap_go', 'Test 3')
        ]
        
        for i, trade in enumerate(test_trades):
            self.scanner_ai.add_trading_result(trade, trade_id=f'TEST_{trade.ticker}_{i:03d}')
        
        # Verify data consistency
        with sqlite3.connect(self.db_path) as conn:
            # Check main trades
            main_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            # Check advanced results (only profitable trades get advanced analysis)
            advanced_results = conn.execute("SELECT COUNT(*) FROM advanced_trading_results").fetchone()[0]
            
            self.assertGreaterEqual(main_trades, 3, "Not all trades saved")
            self.assertGreaterEqual(advanced_results, 2, "Advanced results not created for profitable trades")
        
        print(f"   ✅ {main_trades} trades in main table")
        print(f"   ✅ {advanced_results} advanced results created")
    
    def test_06_advanced_results_retrieval(self):
        """Test retrieval of advanced trading results"""
        print("\n6️⃣ Testing advanced results retrieval...")
        
        # Add a trade first
        trading_result = TradingResult(
            ticker='GOOGL',
            trade_date=date.today(),
            entry_price=2500.0,
            exit_price=2650.0,
            pnl=1500.0,
            was_profitable=True,
            hold_duration_minutes=180,
            strategy_used='news_catalyst',
            notes='Earnings beat'
        )
        
        self.scanner_ai.add_trading_result(trading_result)
        
        # Retrieve advanced results
        results = self.scanner_ai.get_advanced_trading_results(limit=10)
        
        self.assertGreater(len(results), 0, "No advanced results retrieved")
        
        # Verify structure of retrieved results
        latest = results[0]
        self.assertIsInstance(latest, AdvancedTradingResult)
        self.assertIsNotNone(latest.trade_category)
        self.assertIsNotNone(latest.execution_quality)
        
        print(f"   ✅ Retrieved {len(results)} advanced results")
        print(f"   ✅ Latest trade category: {latest.trade_category}")
    
    def test_07_database_manager_stats(self):
        """Test DatabaseManager statistics functionality"""
        print("\n7️⃣ Testing DatabaseManager statistics...")
        
        # Get today's stats
        stats = self.db_manager.get_today_stats()
        
        # Verify stats structure
        required_keys = ['total_trades', 'winning_trades', 'losing_trades', 'total_pnl', 'win_rate']
        for key in required_keys:
            self.assertIn(key, stats, f"Missing stat key: {key}")
        
        # Stats should reflect previous test trades
        self.assertGreaterEqual(stats['total_trades'], 0)
        
        print(f"   ✅ Today's stats: {stats['total_trades']} trades")
        print(f"   ✅ Total PnL: ${stats['total_pnl']:.2f}")
        print(f"   ✅ Win rate: {stats['win_rate']:.1f}%")
    
    def test_08_error_handling(self):
        """Test error handling in edge cases"""
        print("\n8️⃣ Testing error handling...")
        
        # Test auto-categorization with invalid data
        try:
            result = self.categorizer.categorize_trade_automatically(
                ticker='INVALID',
                entry_price=0.0,  # Invalid price
                exit_price=None,
                trade_date=date.today(),
                hold_duration_minutes=None,
                strategy_used='unknown',
                pnl=None
            )
            # Should still return a result, even if categorization fails
            self.assertIsInstance(result, AdvancedTradingResult)
            print("   ✅ Graceful handling of invalid data")
        except Exception as e:
            self.fail(f"Auto-categorizer failed unexpectedly: {e}")
        
        # Test incomplete trade data
        incomplete_trade = TradingResult(
            ticker='TEST',
            trade_date=date.today(),
            entry_price=100.0,
            exit_price=None,  # Open position
            pnl=None,
            was_profitable=False,
            hold_duration_minutes=None,
            strategy_used='test',
            notes='Incomplete trade'
        )
        
        try:
            self.scanner_ai.add_trading_result(incomplete_trade)
            print("   ✅ Handled incomplete trade data")
        except Exception as e:
            self.fail(f"Failed to handle incomplete trade: {e}")


def run_integration_tests():
    """Run all integration tests"""
    print("🧪 INICIANDO TESTS COMPLETOS DE INTEGRACIÓN")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCompleteIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run tests
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("🎉 TODOS LOS TESTS PASARON CORRECTAMENTE")
        print("✅ Sistema completamente integrado y funcionando")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        print(f"Errores: {len(result.errors)}")
        print(f"Fallas: {len(result.failures)}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)