#!/bin/bash
# Run all unit tests for Proactive Scanner system

echo "🧪 Running Unit Tests for Proactive Scanner System"
echo "=================================================="

# Create unit test directory if it doesn't exist
mkdir -p tests/unit

# Run each test module
echo ""
echo "1️⃣ Testing ProactiveScanner Pattern Detection..."
python3 tests/unit/test_proactive_scanner.py

echo ""
echo "2️⃣ Testing Database Integration..."
python3 tests/unit/test_database_integration.py

echo ""
echo "3️⃣ Testing ShortSqueezeWorker Logic..."
python3 tests/unit/test_short_squeeze_worker.py

echo ""
echo "4️⃣ Testing Scanner Integration..."
python3 tests/unit/test_scanner_integration.py

echo ""
echo "=================================================="
echo "✅ All unit tests completed!"
