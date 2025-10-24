#!/usr/bin/env python3
"""
Enable WAL (Write-Ahead Logging) mode for SQLite database
This allows better concurrency - multiple readers + one writer simultaneously
"""

import sqlite3
from pathlib import Path

def enable_wal_mode(db_path: str = "data/pipeline.db"):
    """Enable WAL mode and optimize SQLite for concurrent access"""
    
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    print(f"\n📊 Optimizing database: {db_path}")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current journal mode
        cursor.execute("PRAGMA journal_mode")
        current_mode = cursor.fetchone()[0]
        print(f"Current journal mode: {current_mode}")
        
        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL")
        new_mode = cursor.fetchone()[0]
        print(f"✅ New journal mode: {new_mode}")
        
        # Set busy timeout (wait up to 5 seconds if locked)
        cursor.execute("PRAGMA busy_timeout = 5000")
        print("✅ Busy timeout set to 5000ms")
        
        # Optimize other settings for concurrency
        cursor.execute("PRAGMA synchronous = NORMAL")
        print("✅ Synchronous mode: NORMAL")
        
        cursor.execute("PRAGMA cache_size = -64000")  # 64MB cache
        print("✅ Cache size: 64MB")
        
        cursor.execute("PRAGMA temp_store = MEMORY")
        print("✅ Temp store: MEMORY")
        
        # Verify settings
        print("\n📋 Current Settings:")
        cursor.execute("PRAGMA journal_mode")
        print(f"   Journal mode: {cursor.fetchone()[0]}")
        
        cursor.execute("PRAGMA busy_timeout")
        print(f"   Busy timeout: {cursor.fetchone()[0]}ms")
        
        cursor.execute("PRAGMA synchronous")
        print(f"   Synchronous: {cursor.fetchone()[0]}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ Database optimized for concurrent access!")
        print("\nBenefits:")
        print("  • Multiple processes can read simultaneously")
        print("  • Better write performance")
        print("  • Reduced database locking")
        print("  • 5-second wait on lock (instead of immediate failure)")
        print("=" * 60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        return False


if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/pipeline.db"
    enable_wal_mode(db_path)
