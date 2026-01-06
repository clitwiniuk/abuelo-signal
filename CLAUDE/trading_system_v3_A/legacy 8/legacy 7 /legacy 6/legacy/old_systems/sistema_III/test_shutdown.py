#!/usr/bin/env python3
"""
Test script to verify graceful shutdown behavior
"""

import subprocess
import time
import signal
import sys
import os

def test_shutdown():
    """Test the shutdown behavior"""
    print("🧪 Testing Sistema III shutdown behavior...")

    # Start the system in the background
    print("🚀 Starting Sistema III...")
    process = subprocess.Popen(
        ['python', 'launch_sistema_iii.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for system to initialize
    print("⏱️ Waiting 8 seconds for system initialization...")
    time.sleep(8)

    # Send SIGINT (Ctrl+C)
    print("📡 Sending SIGINT (Ctrl+C)...")
    process.send_signal(signal.SIGINT)

    # Wait for graceful shutdown
    print("⏱️ Waiting for graceful shutdown...")

    try:
        # Wait up to 30 seconds for clean shutdown
        stdout, stderr = process.communicate(timeout=30)

        print("✅ System shut down successfully!")
        print("\n📋 STDERR Output (last 50 lines):")
        stderr_lines = stderr.split('\n')[-50:]
        for line in stderr_lines:
            if line.strip():
                print(line)

        # Check for the specific error we're trying to fix
        if "Error in opportunity message processing" in stderr:
            print("\n❌ Still getting the MessageBus error during shutdown")
            return False
        else:
            print("\n✅ No MessageBus errors detected during shutdown!")
            return True

    except subprocess.TimeoutExpired:
        print("❌ Shutdown took too long, killing process...")
        process.kill()
        return False

if __name__ == "__main__":
    success = test_shutdown()
    sys.exit(0 if success else 1)