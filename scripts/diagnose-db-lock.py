#!/usr/bin/env python3
"""
Diagnose SQLite database locking issues
Shows what's accessing the database and current lock status
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime

def check_database_locks(db_path: str = "data/pipeline.db"):
    """Check for database locks and active connections"""
    
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print(f"\n{'='*60}")
    print(f"🔍 Database Lock Diagnostics")
    print(f"{'='*60}")
    print(f"Database: {db_path.absolute()}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Check file permissions
    print("📁 File Information:")
    stat = db_path.stat()
    print(f"   Size: {stat.st_size / 1024:.2f} KB")
    print(f"   Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Readable: {os.access(db_path, os.R_OK)}")
    print(f"   Writable: {os.access(db_path, os.W_OK)}")
    
    # Check for WAL files
    wal_file = Path(str(db_path) + "-wal")
    shm_file = Path(str(db_path) + "-shm")
    
    print(f"\n📋 WAL Mode Files:")
    print(f"   {db_path.name}-wal: {'✅ EXISTS' if wal_file.exists() else '❌ MISSING'}")
    if wal_file.exists():
        print(f"      Size: {wal_file.stat().st_size / 1024:.2f} KB")
    print(f"   {db_path.name}-shm: {'✅ EXISTS' if shm_file.exists() else '❌ MISSING'}")
    if shm_file.exists():
        print(f"      Size: {shm_file.stat().st_size / 1024:.2f} KB")
    
    # Try to connect and check settings
    try:
        print(f"\n🔌 Connection Test:")
        conn = sqlite3.connect(db_path, timeout=5)
        cursor = conn.cursor()
        
        # Check journal mode
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        print(f"   Journal Mode: {journal_mode}")
        if journal_mode != "wal":
            print(f"   ⚠️  WARNING: Not in WAL mode! Should be 'wal', got '{journal_mode}'")
        
        # Check busy timeout
        cursor.execute("PRAGMA busy_timeout")
        busy_timeout = cursor.fetchone()[0]
        print(f"   Busy Timeout: {busy_timeout}ms")
        
        # Check synchronous mode
        cursor.execute("PRAGMA synchronous")
        sync_mode = cursor.fetchone()[0]
        sync_names = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}
        print(f"   Synchronous: {sync_names.get(sync_mode, sync_mode)}")
        
        # Check locking mode
        cursor.execute("PRAGMA locking_mode")
        locking_mode = cursor.fetchone()[0]
        print(f"   Locking Mode: {locking_mode}")
        
        # Check database list
        cursor.execute("PRAGMA database_list")
        databases = cursor.fetchall()
        print(f"\n📊 Attached Databases:")
        for db in databases:
            print(f"   {db[1]}: {db[2]}")
        
        # Check if database is locked by trying a write
        print(f"\n🔒 Lock Status:")
        try:
            cursor.execute("BEGIN IMMEDIATE")
            print(f"   ✅ Can acquire write lock")
            cursor.execute("ROLLBACK")
        except sqlite3.OperationalError as e:
            print(f"   ❌ Cannot acquire write lock: {e}")
            print(f"   🔴 DATABASE IS CURRENTLY LOCKED!")
        
        # Get table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n📋 Tables ({len(tables)}):")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"   {table[0]}: {count} rows")
        
        conn.close()
        print(f"\n✅ Connection test completed")
        
    except sqlite3.OperationalError as e:
        print(f"\n❌ Connection failed: {e}")
        if "database is locked" in str(e):
            print(f"\n🔴 DATABASE IS LOCKED!")
            print(f"\nPossible causes:")
            print(f"   1. Another process has an open transaction")
            print(f"   2. DB Browser for SQLite is open with this database")
            print(f"   3. Multiple API instances running")
            print(f"   4. Crashed process left lock file")
            print(f"\nSolutions:")
            print(f"   1. Close DB Browser for SQLite")
            print(f"   2. Restart API server")
            print(f"   3. Check for multiple Python processes:")
            print(f"      Get-Process python | Where-Object {{$_.Path -like '*ai-ewg*'}}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    
    # Check for open file handles (Windows)
    if sys.platform == "win32":
        print(f"\n🔍 Checking for open handles (Windows)...")
        print(f"   Run this command to see processes with database open:")
        print(f"   handle.exe {db_path.absolute()}")
        print(f"   (Download handle.exe from: https://learn.microsoft.com/en-us/sysinternals/downloads/handle)")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/pipeline.db"
    check_database_locks(db_path)
