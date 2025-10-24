#!/usr/bin/env python3
"""
Checkpoint WAL file to release locks
"""
import sqlite3
import sys
from pathlib import Path

def checkpoint_wal(db_path: str = "data/pipeline.db"):
    db_path = Path(db_path)
    
    print(f"\n🔄 Checkpointing WAL file for: {db_path}")
    
    try:
        # Use a very short timeout to avoid hanging
        conn = sqlite3.connect(db_path, timeout=1)
        
        # Try to checkpoint
        cursor = conn.cursor()
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        result = cursor.fetchone()
        
        print(f"✅ Checkpoint result: {result}")
        print(f"   Busy: {result[0]}")
        print(f"   Log frames: {result[1]}")
        print(f"   Checkpointed frames: {result[2]}")
        
        conn.close()
        print(f"✅ WAL checkpoint completed\n")
        
    except sqlite3.OperationalError as e:
        print(f"❌ Cannot checkpoint: {e}")
        print(f"\nThe database is locked by another process.")
        print(f"Please close all applications accessing the database.\n")
        return False
    
    return True

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/pipeline.db"
    checkpoint_wal(db_path)
