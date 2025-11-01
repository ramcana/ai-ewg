"""Check episode data for debugging clip rendering issues"""
import sqlite3
from pathlib import Path

# Connect to database
conn = sqlite3.connect('data/pipeline.db')
cursor = conn.cursor()

# First check schema
cursor.execute("PRAGMA table_info(episodes)")
columns = cursor.fetchall()
print("Episode table columns:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")
print()

# Check clips table schema
cursor.execute("PRAGMA table_info(clips)")
clip_columns = cursor.fetchall()
print("Clips table columns:")
for col in clip_columns:
    print(f"  - {col[1]} ({col[2]})")
print()

# Get episode data
episode_id = 'temp-uploaded-fd1314_10-27-25'
cursor.execute('''
    SELECT id, source_path, stage, metadata
    FROM episodes 
    WHERE id = ?
''', (episode_id,))

result = cursor.fetchone()

if result:
    import json
    ep_id, source_path, stage, metadata_json = result
    
    print(f"Episode ID: {ep_id}")
    print(f"Source Path: {source_path}")
    print(f"Processing Stage: {stage}")
    print(f"Source Exists: {Path(source_path).exists() if source_path else 'N/A'}")
    
    # Parse metadata
    if metadata_json:
        metadata = json.loads(metadata_json)
        has_transcription = bool(metadata.get('transcription'))
        has_enrichment = bool(metadata.get('enrichment'))
        print(f"Has Transcription: {has_transcription}")
        print(f"Has Enrichment: {has_enrichment}")
        if has_transcription:
            print(f"Transcription text length: {len(metadata['transcription'].get('text', ''))} chars")
    else:
        print("No metadata")
    
    # Check clips
    cursor.execute('SELECT id, start_ms, end_ms, status FROM clips WHERE episode_id = ?', (ep_id,))
    clips = cursor.fetchall()
    print(f"\nClips: {len(clips)}")
    for clip_id, start, end, status in clips:
        start_sec = start / 1000
        end_sec = end / 1000
        duration_sec = (end - start) / 1000
        print(f"  - {clip_id}: {start_sec:.1f}s - {end_sec:.1f}s (duration: {duration_sec:.1f}s) [{status}]")
    
    # Get video duration from metadata
    cursor.execute('SELECT duration_seconds FROM episodes WHERE id = ?', (ep_id,))
    duration_result = cursor.fetchone()
    if duration_result and duration_result[0]:
        video_duration = duration_result[0]
        print(f"\nVideo Duration: {video_duration:.1f}s ({video_duration/60:.1f} minutes)")
        print(f"⚠️  Clips are BEYOND video duration!" if clips and clips[0][1]/1000 > video_duration else "✓ Clips are within video duration")
else:
    print(f"Episode {episode_id} not found")

conn.close()
