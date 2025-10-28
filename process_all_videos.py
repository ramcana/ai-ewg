"""
Batch process all videos in the configured source directories
"""
import requests
import json
import time
import threading
from pathlib import Path

API_URL = "http://localhost:8000"

def show_progress_indicator(stop_event):
    """Show a progress indicator while processing"""
    chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    while not stop_event.is_set():
        print(f'\r  {chars[i % len(chars)]} Processing... (this may take 30-60 minutes)', end='', flush=True)
        i += 1
        time.sleep(0.1)
    print('\r' + ' ' * 80 + '\r', end='', flush=True)  # Clear the line

def discover_videos():
    """Discover all videos in source directories"""
    print("🔍 Discovering videos...")
    
    try:
        response = requests.post(f"{API_URL}/episodes/discover")
        if response.status_code == 200:
            data = response.json()
            episodes = data.get('episodes', [])
            print(f"✅ Found {len(episodes)} video(s)")
            
            for ep in episodes:
                episode_id = ep.get('episode_id', 'unknown')
                title = ep.get('title', 'Unknown Title')
                source = ep.get('source_path', 'Unknown')
                print(f"   📹 {episode_id}: {title}")
                print(f"      Source: {source}")
            
            return episodes
        else:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return []
    except Exception as e:
        print(f"❌ Error discovering videos: {e}")
        return []

def process_episode(episode_id, force_reprocess=False):
    """Process a single episode"""
    print(f"\n{'='*70}")
    print(f"🎬 Processing: {episode_id}")
    print(f"{'='*70}")
    print(f"⏱️  Note: This may take 30-60 minutes per video (no timeout)")
    
    payload = {
        "episode_id": episode_id,
        "force_reprocess": force_reprocess,
        "clear_cache": False
    }
    
    start_time = time.time()
    
    # Start progress indicator in background thread
    stop_event = threading.Event()
    progress_thread = threading.Thread(target=show_progress_indicator, args=(stop_event,))
    progress_thread.daemon = True
    progress_thread.start()
    
    try:
        # No timeout - let it run as long as needed
        response = requests.post(
            f"{API_URL}/episodes/process",
            json=payload,
            timeout=None  # No timeout!
        )
        duration = time.time() - start_time
        
        # Stop progress indicator
        stop_event.set()
        progress_thread.join(timeout=1)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Processing complete in {duration:.1f}s ({duration/60:.1f} min)")
            
            if data.get('success'):
                # API returns data directly, not wrapped in 'result'
                print(f"\n📊 Results:")
                print(f"   Episode ID: {data.get('episode_id')}")
                print(f"   Stage: {data.get('stage')}")
                print(f"   Duration: {data.get('duration', 0):.1f}s")
                
                if data.get('metadata'):
                    meta = data['metadata']
                    print(f"   Title: {meta.get('title', 'N/A')}")
                    print(f"   Show: {meta.get('show', 'N/A')}")
                    if meta.get('duration'):
                        print(f"   Video Duration: {meta.get('duration', 0)/60:.1f} minutes")
                
                if data.get('error'):
                    print(f"   ⚠️  Error: {data.get('error')}")
                
                return True
            else:
                print(f"❌ Processing failed: {data.get('error')}")
                return False
        else:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        # Stop progress indicator
        stop_event.set()
        progress_thread.join(timeout=1)
        
        print(f"❌ Error processing episode: {e}")
        return False

def main():
    print("="*70)
    print("AI-EWG Batch Video Processing")
    print("="*70)
    print()
    
    # Step 1: Discover all videos
    episodes = discover_videos()
    
    if not episodes:
        print("\n❌ No videos found to process")
        print("💡 Make sure videos are in organized input folders:")
        print("   - input_videos/TheNewsForum/ForumDailyNews/")
        print("   - input_videos/_uncategorized/")
        return
    
    print(f"\n📋 Found {len(episodes)} video(s) to process")
    print()
    
    # Ask for confirmation
    response = input(f"Process all {len(episodes)} video(s)? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Cancelled")
        return
    
    # Step 2: Process each episode
    successful = 0
    failed = 0
    
    for i, episode in enumerate(episodes, 1):
        episode_id = episode.get('episode_id')
        
        print(f"\n{'='*70}")
        print(f"Processing {i}/{len(episodes)}: {episode_id}")
        print(f"{'='*70}")
        
        if process_episode(episode_id):
            successful += 1
        else:
            failed += 1
        
        # Brief pause between episodes
        if i < len(episodes):
            print("\n⏸️  Pausing 5 seconds before next episode...")
            time.sleep(5)
    
    # Final summary
    print("\n" + "="*70)
    print("Batch Processing Complete!")
    print("="*70)
    print(f"\n📊 Summary:")
    print(f"   Total: {len(episodes)}")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print()
    
    if successful > 0:
        print("Next steps:")
        print("  1. View results in Streamlit dashboard")
        print("  2. Generate clips: python process_clips.py")
        print("  3. Create social packages in dashboard")

if __name__ == "__main__":
    main()
