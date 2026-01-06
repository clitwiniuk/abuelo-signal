#!/usr/bin/env python3
"""
Streamlit v4.0 Interface Test Suite
Tests the unified Trading & Scanner interface functionality
"""

import sys
import os
import subprocess
import time
import requests
import threading
import logging
from pathlib import Path
from datetime import datetime
import signal

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger("StreamlitV4Test")
logging.basicConfig(level=logging.INFO)

class StreamlitV4InterfaceTest:
    """Test suite for Streamlit v4.0 interface"""
    
    def __init__(self):
        self.streamlit_process = None
        self.test_results = []
        self.base_url = "http://localhost:8505"
    
    def test_file_structure(self):
        """Test 1: Verify file structure and content"""
        logger.info("🧪 Test 1: File Structure and Content")
        
        v4_path = project_root / "streamlit_app_v4.py"
        
        # Check file exists
        file_exists = v4_path.exists()
        logger.info(f"   streamlit_app_v4.py exists: {'✅' if file_exists else '❌'}")
        
        if not file_exists:
            self.test_results.append({'test': 'file_structure', 'passed': False, 'error': 'File not found'})
            return
        
        # Read and analyze content
        with open(v4_path, 'r') as f:
            content = f.read()
        
        # Check for key components
        checks = {
            'streamlit_import': 'import streamlit as st' in content,
            'nest_asyncio_fix': 'nest_asyncio.apply()' in content,
            'scanner_intelligence': 'ScannerIntelligence' in content,
            'trading_config': 'TradingConfig' in content,
            'unified_interface': 'Trading & Scanner' in content,
            'auto_add_functionality': 'auto_add' in content.lower(),
            'ml_scoring': 'ml_score' in content.lower(),
            'sentiment_filter': 'sentiment_filter' in content.lower(),
            'learning_system': 'learning' in content.lower(),
            'error_handling': 'try:' in content and 'except' in content,
            'session_state': 'st.session_state' in content,
            'tabs_structure': 'st.tabs(' in content
        }
        
        for check_name, passed in checks.items():
            logger.info(f"   {check_name}: {'✅' if passed else '❌'}")
            self.test_results.append({
                'test': f'file_structure_{check_name}',
                'passed': passed
            })
    
    def test_imports_and_syntax(self):
        """Test 2: Test imports and syntax validation"""
        logger.info("🧪 Test 2: Imports and Syntax Validation")
        
        v4_path = project_root / "streamlit_app_v4.py"
        
        try:
            # Test Python syntax
            result = subprocess.run([
                sys.executable, '-m', 'py_compile', str(v4_path)
            ], capture_output=True, text=True, cwd=project_root)
            
            syntax_valid = result.returncode == 0
            logger.info(f"   Python syntax valid: {'✅' if syntax_valid else '❌'}")
            
            if not syntax_valid:
                logger.error(f"   Syntax error: {result.stderr}")
            
            self.test_results.append({
                'test': 'syntax_validation',
                'passed': syntax_valid,
                'error': result.stderr if not syntax_valid else None
            })
            
        except Exception as e:
            logger.error(f"   Syntax validation failed: {e}")
            self.test_results.append({
                'test': 'syntax_validation', 
                'passed': False,
                'error': str(e)
            })
    
    def start_streamlit_server(self):
        """Start Streamlit server in background"""
        logger.info("🚀 Starting Streamlit v4.0 server...")
        
        try:
            # Start Streamlit process
            self.streamlit_process = subprocess.Popen([
                sys.executable, '-m', 'streamlit', 'run', 
                'streamlit_app_v4.py',
                '--server.port=8505',
                '--server.headless=true',
                '--browser.gatherUsageStats=false'
            ], 
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
            )
            
            # Wait for server to start
            max_wait = 30
            wait_time = 0
            
            while wait_time < max_wait:
                try:
                    response = requests.get(f"{self.base_url}/healthz", timeout=2)
                    if response.status_code == 200:
                        logger.info(f"   ✅ Streamlit server started on {self.base_url}")
                        return True
                except requests.exceptions.RequestException:
                    pass
                
                time.sleep(2)
                wait_time += 2
                logger.info(f"   Waiting for server... ({wait_time}s)")
            
            logger.error("   ❌ Streamlit server failed to start within 30 seconds")
            return False
            
        except Exception as e:
            logger.error(f"   ❌ Failed to start Streamlit server: {e}")
            return False
    
    def test_server_startup(self):
        """Test 3: Server startup and basic connectivity"""
        logger.info("🧪 Test 3: Server Startup and Connectivity")
        
        server_started = self.start_streamlit_server()
        
        if server_started:
            # Test basic connectivity
            try:
                response = requests.get(self.base_url, timeout=10)
                accessible = response.status_code == 200
                logger.info(f"   Server accessible: {'✅' if accessible else '❌'}")
                
                self.test_results.append({
                    'test': 'server_startup',
                    'passed': accessible,
                    'status_code': response.status_code
                })
                
            except Exception as e:
                logger.error(f"   Server access failed: {e}")
                self.test_results.append({
                    'test': 'server_startup',
                    'passed': False,
                    'error': str(e)
                })
        else:
            self.test_results.append({
                'test': 'server_startup',
                'passed': False,
                'error': 'Server failed to start'
            })
    
    def test_streamlit_logs(self):
        """Test 4: Check Streamlit startup logs for errors"""
        logger.info("🧪 Test 4: Startup Logs Analysis")
        
        if not self.streamlit_process:
            logger.info("   No Streamlit process to check logs")
            return
        
        # Give it a moment to generate logs
        time.sleep(3)
        
        try:
            # Check if process is still running
            poll_result = self.streamlit_process.poll()
            process_running = poll_result is None
            
            logger.info(f"   Streamlit process running: {'✅' if process_running else '❌'}")
            
            # Try to read any stderr output
            if self.streamlit_process.stderr:
                try:
                    # Use a shorter timeout for non-blocking read
                    stderr_output = self.streamlit_process.stderr.read()
                    if stderr_output:
                        logger.info(f"   Stderr output detected: {len(stderr_output)} characters")
                        # Check for common error patterns
                        error_patterns = ['ImportError', 'ModuleNotFoundError', 'SyntaxError', 'Exception']
                        has_errors = any(pattern in stderr_output for pattern in error_patterns)
                        logger.info(f"   Critical errors in logs: {'❌' if has_errors else '✅'}")
                    else:
                        logger.info("   No stderr output (good)")
                except:
                    logger.info("   Could not read stderr (likely still running)")
            
            self.test_results.append({
                'test': 'startup_logs',
                'passed': process_running,
                'process_status': poll_result
            })
            
        except Exception as e:
            logger.error(f"   Log analysis failed: {e}")
            self.test_results.append({
                'test': 'startup_logs',
                'passed': False,
                'error': str(e)
            })
    
    def test_interface_components(self):
        """Test 5: Test interface components via HTTP requests"""
        logger.info("🧪 Test 5: Interface Components")
        
        if not self.streamlit_process or self.streamlit_process.poll() is not None:
            logger.info("   Streamlit server not running, skipping interface tests")
            return
        
        try:
            # Test main page load
            response = requests.get(self.base_url, timeout=10)
            main_page_loads = response.status_code == 200
            logger.info(f"   Main page loads: {'✅' if main_page_loads else '❌'}")
            
            # Check for key interface elements in response
            if main_page_loads:
                content = response.text
                
                # Look for expected interface elements
                interface_checks = {
                    'trading_scanner_tab': 'Trading & Scanner' in content,
                    'analytics_section': 'Analytics' in content or 'Performance' in content,
                    'scanner_functionality': 'scanner' in content.lower(),
                    'ml_elements': 'ml' in content.lower() or 'machine' in content.lower(),
                    'streamlit_elements': 'streamlit' in content.lower()
                }
                
                for check_name, found in interface_checks.items():
                    logger.info(f"   {check_name}: {'✅' if found else '❌'}")
                    self.test_results.append({
                        'test': f'interface_{check_name}',
                        'passed': found
                    })
            
            self.test_results.append({
                'test': 'main_page_load',
                'passed': main_page_loads,
                'status_code': response.status_code if main_page_loads else None
            })
            
        except Exception as e:
            logger.error(f"   Interface component test failed: {e}")
            self.test_results.append({
                'test': 'interface_components',
                'passed': False,
                'error': str(e)
            })
    
    def test_database_integration(self):
        """Test 6: Database integration and data flow"""
        logger.info("🧪 Test 6: Database Integration")
        
        try:
            # Test database manager import and initialization
            from core.database_manager import get_database_manager
            
            db_manager = get_database_manager()
            database_accessible = True
            logger.info(f"   Database manager accessible: ✅")
            
            # Test basic database operations
            try:
                # Test strategy performance query (the one we fixed)
                performance_data = db_manager.get_strategy_performance(30)
                performance_query_works = True
                logger.info(f"   Strategy performance query: ✅")
            except Exception as e:
                performance_query_works = False
                logger.error(f"   Strategy performance query: ❌ - {e}")
            
            # Test basic queries
            try:
                from core.database_manager import DatabaseManager
                import sqlite3
                
                conn = sqlite3.connect(db_manager.db_path)
                cursor = conn.cursor()
                
                # Test trades table access
                cursor.execute("SELECT COUNT(*) FROM trades")
                trade_count = cursor.fetchone()[0]
                logger.info(f"   Trades table accessible: ✅ ({trade_count} trades)")
                
                # Test our fixed query
                cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl IS NOT NULL")
                closed_trades = cursor.fetchone()[0]
                logger.info(f"   Closed trades query: ✅ ({closed_trades} closed)")
                
                conn.close()
                
                database_queries_work = True
                
            except Exception as e:
                database_queries_work = False
                logger.error(f"   Database queries failed: {e}")
            
            self.test_results.append({
                'test': 'database_integration',
                'passed': database_accessible and performance_query_works and database_queries_work,
                'database_accessible': database_accessible,
                'performance_query_works': performance_query_works,
                'database_queries_work': database_queries_work
            })
            
        except Exception as e:
            logger.error(f"   Database integration test failed: {e}")
            self.test_results.append({
                'test': 'database_integration',
                'passed': False,
                'error': str(e)
            })
    
    def stop_streamlit_server(self):
        """Stop Streamlit server"""
        if self.streamlit_process:
            logger.info("🛑 Stopping Streamlit server...")
            try:
                self.streamlit_process.terminate()
                self.streamlit_process.wait(timeout=10)
                logger.info("   ✅ Streamlit server stopped")
            except subprocess.TimeoutExpired:
                logger.info("   Force killing Streamlit server...")
                self.streamlit_process.kill()
                self.streamlit_process.wait()
            except Exception as e:
                logger.error(f"   Error stopping server: {e}")
    
    def run_all_tests(self):
        """Run all Streamlit v4.0 interface tests"""
        logger.info("🚀 Starting Streamlit v4.0 Interface Test Suite")
        logger.info("=" * 60)
        
        try:
            self.test_file_structure()
            logger.info("-" * 40)
            
            self.test_imports_and_syntax()
            logger.info("-" * 40)
            
            self.test_server_startup()
            logger.info("-" * 40)
            
            if self.streamlit_process and self.streamlit_process.poll() is None:
                self.test_streamlit_logs()
                logger.info("-" * 40)
                
                self.test_interface_components()
                logger.info("-" * 40)
            
            self.test_database_integration()
            
            self.print_summary()
            
        finally:
            self.stop_streamlit_server()
    
    def print_summary(self):
        """Print test summary"""
        logger.info("📊 STREAMLIT V4.0 INTERFACE TEST SUMMARY")
        logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.get('passed', False))
        failed_tests = total_tests - passed_tests
        
        logger.info(f"📈 Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        
        if total_tests > 0:
            pass_rate = (passed_tests / total_tests) * 100
            logger.info(f"📊 Pass Rate: {pass_rate:.1f}%")
        
        # Group results by test category
        test_categories = {}
        for result in self.test_results:
            test_name = result['test']
            category = test_name.split('_')[0] if '_' in test_name else test_name
            
            if category not in test_categories:
                test_categories[category] = {'passed': 0, 'total': 0}
            
            test_categories[category]['total'] += 1
            if result.get('passed', False):
                test_categories[category]['passed'] += 1
        
        logger.info("\n📋 Test Categories:")
        for category, stats in test_categories.items():
            logger.info(f"   {category}: {stats['passed']}/{stats['total']}")
        
        # Show failed tests
        failed_results = [r for r in self.test_results if not r.get('passed', False)]
        if failed_results:
            logger.info("\n❌ Failed Tests:")
            for result in failed_results:
                error = result.get('error', 'No error details')
                logger.info(f"   • {result['test']}: {error}")
        
        overall_success = failed_tests == 0
        status = "🎉 ALL STREAMLIT TESTS PASSED!" if overall_success else "⚠️  SOME STREAMLIT TESTS FAILED"
        logger.info(f"\n{status}")
        
        return overall_success

def main():
    """Main test runner"""
    test_suite = StreamlitV4InterfaceTest()
    success = test_suite.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())