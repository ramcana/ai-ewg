"""
Migrate clip output paths from data/outputs to data/clips

This script updates all clip specifications in the database to use the new
data/clips path structure instead of the old data/outputs structure.
"""

import sqlite3
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def migrate_clip_paths(db_path: str = "data/pipeline.db"):
    """
    Migrate clip output paths in database
    
    Args:
        db_path: Path to database file
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print(f"📊 Migrating clip paths in: {db_path}")
    print()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get all clips with variants
        cursor.execute("SELECT id, episode_id, variants FROM clips WHERE variants IS NOT NULL")
        clips = cursor.fetchall()
        
        print(f"Found {len(clips)} clips with variants")
        print()
        
        updated_count = 0
        
        for clip_id, episode_id, variants_json in clips:
            try:
                variants = json.loads(variants_json)
                
                # Check if any variant has old path
                needs_update = False
                for variant in variants:
                    if 'output_path' in variant:
                        old_path = variant['output_path']
                        if 'data/outputs' in old_path or 'data\\outputs' in old_path:
                            needs_update = True
                            break
                
                if not needs_update:
                    continue
                
                # Update paths
                for variant in variants:
                    if 'output_path' in variant:
                        old_path = variant['output_path']
                        # Replace data/outputs with data/clips
                        new_path = old_path.replace('data/outputs', 'data/clips')
                        new_path = new_path.replace('data\\outputs', 'data\\clips')
                        
                        if new_path != old_path:
                            print(f"  Clip {clip_id}:")
                            print(f"    Old: {old_path}")
                            print(f"    New: {new_path}")
                            variant['output_path'] = new_path
                
                # Update database
                new_variants_json = json.dumps(variants)
                cursor.execute(
                    "UPDATE clips SET variants = ? WHERE id = ?",
                    (new_variants_json, clip_id)
                )
                
                updated_count += 1
                
            except json.JSONDecodeError as e:
                print(f"  ⚠️  Skipping clip {clip_id}: Invalid JSON - {e}")
                continue
            except Exception as e:
                print(f"  ⚠️  Error updating clip {clip_id}: {e}")
                continue
        
        # Commit changes
        conn.commit()
        
        print()
        print("=" * 80)
        print(f"✅ Migration completed!")
        print(f"   Updated {updated_count} clips")
        print()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate clip paths from data/outputs to data/clips")
    parser.add_argument("--db", default="data/pipeline.db", help="Path to database file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    migrate_clip_paths(args.db)
    
    if not args.dry_run:
        print("💡 Tip: You can now optionally move the actual clip files:")
        print("   Run: .\\scripts\\migrate_clips_to_new_location.ps1")
        print()
