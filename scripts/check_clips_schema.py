"""Check clips table schema"""
import sqlite3
from pathlib import Path

db_path = Path("data/pipeline.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Clips table columns:")
cursor.execute('PRAGMA table_info(clips)')
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")

print("\nSample clip data:")
cursor.execute('SELECT * FROM clips LIMIT 1')
columns = [desc[0] for desc in cursor.description]
print(f"Columns: {columns}")

row = cursor.fetchone()
if row:
    for col, val in zip(columns, row):
        if val and len(str(val)) > 100:
            print(f"  {col}: {str(val)[:100]}...")
        else:
            print(f"  {col}: {val}")

conn.close()
