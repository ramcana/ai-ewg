"""
Complete cleanup script - clears ALL databases, backups, and generated data
IMPORTANT: Stop the API server before running this!
"""
import os
import shutil
from pathlib import Path
import glob

print("=" * 60)
print("COMPLETE DATA CLEANUP")
print("=" * 60)
print("\n⚠️  WARNING: This will delete:")
print("  - All database files (including backups)")
print("  - All enriched data")
print("  - All rendered HTML")
print("  - All audio files")
print("  - All transcripts")
print("  - All intelligence cache")
print("  - Test output files")
print("\n⚠️  Make sure the API server is STOPPED before continuing!")
print("\nPress Ctrl+C to cancel, or Enter to continue...")
input()

cleared_count = 0
error_count = 0

# 1. Database files in data/
print("\n📁 Clearing database files...")
db_files = [
    "data/pipeline.db",
    "data/pipeline.db-shm",
    "data/pipeline.db-wal",
    "data/pipeline.db.backup"
]

for file_path in db_files:
    path = Path(file_path)
    try:
        if path.exists():
            path.unlink()
            print(f"  ✅ Deleted: {path}")
            cleared_count += 1
    except Exception as e:
        print(f"  ❌ Error: {path} - {e}")
        error_count += 1

# 2. Database backup files in root
print("\n📁 Clearing database backups...")
backup_files = glob.glob("pipeline_backup_*.db")
for file_path in backup_files:
    try:
        Path(file_path).unlink()
        print(f"  ✅ Deleted: {file_path}")
        cleared_count += 1
    except Exception as e:
        print(f"  ❌ Error: {file_path} - {e}")
        error_count += 1

# 3. Data directories
print("\n📁 Clearing data directories...")
data_dirs = [
    "data/enriched",
    "data/public",
    "data/audio",
    "data/transcripts",
    "data/intelligence_cache",
    "data/cache",
    "data/meta"
]

for dir_path in data_dirs:
    path = Path(dir_path)
    try:
        if path.exists():
            shutil.rmtree(path)
            print(f"  ✅ Deleted: {path}")
            cleared_count += 1
    except Exception as e:
        print(f"  ❌ Error: {path} - {e}")
        error_count += 1

# 4. Test output files
print("\n📁 Clearing test output files...")
test_files = [
    "test_output.html",
    "test_output_phase2.html",
    "test_phase2.html"
]

for file_path in test_files:
    path = Path(file_path)
    try:
        if path.exists():
            path.unlink()
            print(f"  ✅ Deleted: {path}")
            cleared_count += 1
    except Exception as e:
        print(f"  ❌ Error: {path} - {e}")
        error_count += 1

# Summary
print("\n" + "=" * 60)
print("CLEANUP COMPLETE!")
print(f"  ✅ Cleared: {cleared_count} items")
if error_count > 0:
    print(f"  ❌ Errors: {error_count} items")
    print("\n⚠️  If you see 'process cannot access' errors:")
    print("     1. Stop the API server (Ctrl+C)")
    print("     2. Run this script again")
else:
    print(f"  🎉 All clean!")
print("=" * 60)

print("\n📋 Next Steps:")
print("1. Restart API server: .\\start-api-server.ps1")
print("2. Run test: python test_process.py")
print("3. Fresh processing with Phase 2!")
