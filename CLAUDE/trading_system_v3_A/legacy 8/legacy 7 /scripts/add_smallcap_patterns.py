
import sqlite3
import os

DB_PATH = 'trading_data.db'

def add_patterns():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    print(f"🔧 Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Small Cap Patterns to add
    new_patterns = [
        # Short Setups (Red/Orange/Purple)
        ('Parabolic Short', 'Vertical move exhaustion, sell setup', '#ef4444'), # Red
        ('Death Candle', 'Huge red candle wiping out gains', '#b91c1c'), # Dark Red
        ('Late Day Fade', 'Failed breakout fading into close', '#f97316'), # Orange
        ('Gap and Crap', 'Gaps up but sells off immediately', '#db2777'), # Pink

        # Long Setups (Green/Blue/Cyan)
        ('VWAP Reclaim', 'Price crosses back above VWAP with volume', '#06b6d4'), # Cyan
        ('Flat Top Breakout', 'Consolidation under resistance, then break', '#22c55e'), # Green
        ('Red to Green', 'Reclaiming previous day close', '#10b981'), # Emerald
        ('ABCD Pattern', 'Impulse, Pullback, Extension', '#3b82f6'), # Blue
        ('Morning Dip Buy', 'Sharp drop at open finding support', '#84cc16'), # Lime
        ('Multi-Day Breakout', 'Breaking resistance level from prior days', '#6366f1'), # Indigo
        ('Micro Pullback', 'Small pullback in strong trend', '#8b5cf6'), # Violet
        ('Volume Exhaustion', 'Climactic volume indicating top/bottom', '#eab308') # Yellow
    ]

    print(f"Adding {len(new_patterns)} new Small Cap patterns...")
    
    cursor.executemany(
        'INSERT OR IGNORE INTO custom_patterns (name, description, color) VALUES (?, ?, ?)',
        new_patterns
    )

    conn.commit()
    conn.close()
    print("✅ New patterns added successfully!")

if __name__ == "__main__":
    add_patterns()
