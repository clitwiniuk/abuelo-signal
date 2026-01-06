
import sqlite3
import os

DB_PATH = 'trading_data.db'

def init_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    print(f"🔧 Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create pattern_labels table
    print("Creating pattern_labels table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pattern_labels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        date TEXT NOT NULL,
        pattern_name TEXT NOT NULL,
        is_match INTEGER DEFAULT 1,
        start_bar INTEGER,
        end_bar INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, date, pattern_name)
    )
    ''')

    # Create custom_patterns table
    print("Creating custom_patterns table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS custom_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        color TEXT DEFAULT '#3b82f6',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Insert default patterns if empty
    cursor.execute('SELECT COUNT(*) FROM custom_patterns')
    count = cursor.fetchone()[0]
    if count == 0:
        print("Inserting default patterns...")
        default_patterns = [
            ('Flag', 'Bullish Flag Pattern', '#10b981'),
            ('Pennant', 'Bullish Pennant', '#3b82f6'),
            ('Double Bottom', 'Reversal Pattern', '#8b5cf6'),
            ('Cup and Handle', 'Bullish Continuation', '#f59e0b'),
            ('Head and Shoulders', 'Reversal Pattern', '#ef4444')
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO custom_patterns (name, description, color) VALUES (?, ?, ?)',
            default_patterns
        )

    conn.commit()
    conn.close()
    print("✅ Database initialization complete!")

if __name__ == "__main__":
    init_db()
