"""
Test script to process an episode and verify Phase 2 integration
"""
import requests
import json
import time

API_URL = "http://localhost:8000"

def discover_episodes():
    """Discover episodes"""
    print("🔍 Discovering episodes...")
    response = requests.post(f"{API_URL}/episodes/discover")
    data = response.json()
    print(f"✅ Found {data.get('discovered_count', 0)} episodes")
    print(json.dumps(data, indent=2))
    return data

def process_episode(episode_id):
    """Process a single episode"""
    print(f"\n🚀 Processing episode: {episode_id}")
    print("⏱️  This will take 5-10 minutes (transcription + enrichment + rendering)...")
    
    payload = {
        "episode_id": episode_id,
        "force_reprocess": False
    }
    
    start_time = time.time()
    response = requests.post(
        f"{API_URL}/episodes/process",
        json=payload,
        timeout=3600  # 1 hour timeout
    )
    duration = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Processing complete in {duration:.1f} seconds ({duration/60:.1f} minutes)")
        
        # Check for Phase 2 features
        if data.get('success'):
            print(f"   Stage: {data.get('stage')}")
            
            # Check if HTML was generated
            outputs = data.get('outputs', {})
            if outputs.get('rendered_html'):
                html_path = outputs.get('html_path', 'unknown')
                print(f"   HTML: {html_path}")
                
                # Check for Phase 2 features in HTML
                html_content = outputs['rendered_html']
                has_guests = 'Featured Guests' in html_content
                has_badges = 'credibility-badge' in html_content
                has_verified = 'Verified Expert' in html_content or 'Identified Contributor' in html_content
                
                print(f"\n📊 Phase 2 Integration Check:")
                print(f"   Guest Section: {'✅ YES' if has_guests else '❌ NO'}")
                print(f"   Credibility Badges: {'✅ YES' if has_badges else '❌ NO'}")
                print(f"   Verified Experts: {'✅ YES' if has_verified else '❌ NO'}")
                
                # Save HTML to file
                with open('test_output.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"\n💾 HTML saved to: test_output.html")
            
            # Check metadata
            metadata = data.get('metadata', {})
            if metadata:
                print(f"\n📝 Metadata:")
                print(f"   Show: {metadata.get('show_name', 'Unknown')}")
                print(f"   Title: {metadata.get('title', 'Unknown')}")
                print(f"   Host: {metadata.get('host', 'Unknown')}")
                guests = metadata.get('guests', [])
                if guests is not None:
                    print(f"   Guests: {len(guests)}")
                else:
                    print(f"   Guests: 0")
        else:
            print(f"❌ Processing failed: {data.get('error')}")
        
        return data
    else:
        print(f"❌ API Error: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("AI-EWG Phase 2 Integration Test")
    print("=" * 60)
    
    # Step 1: Discover episodes
    discovery = discover_episodes()
    
    if discovery and discovery.get('episodes'):
        # Get first episode
        episode = discovery['episodes'][0]
        episode_id = episode.get('episode_id')
        
        if episode_id:
            # Step 2: Process episode
            result = process_episode(episode_id)
            
            print("\n" + "=" * 60)
            print("Test Complete!")
            print("=" * 60)
        else:
            print("❌ No episode_id found")
    else:
        print("❌ No episodes discovered")
