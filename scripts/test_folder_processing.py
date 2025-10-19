#!/usr/bin/env python3
"""
Test script for folder-based video processing via n8n webhook

This script triggers the n8n workflow to process all videos in a specified folder.
"""

import requests
import json
import sys
from pathlib import Path

def trigger_folder_processing(webhook_url, folder_path="test_videos/newsroom/2024", target_stage="rendered"):
    """
    Trigger n8n workflow to process all videos in a folder
    
    Args:
        webhook_url: The n8n webhook URL
        folder_path: Path to folder containing videos
        target_stage: Target processing stage (discovered, prepped, transcribed, enriched, rendered)
    """
    
    payload = {
        "folder_path": folder_path,
        "process_all": True,
        "target_stage": target_stage,
        "trigger_source": "test_script"
    }
    
    print(f"🎬 Triggering folder processing...")
    print(f"   Folder: {folder_path}")
    print(f"   Target Stage: {target_stage}")
    print(f"   Webhook: {webhook_url}")
    print()
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Workflow triggered successfully!")
            print(f"   Response: {response.text}")
            return True
        else:
            print(f"❌ Failed to trigger workflow")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error triggering workflow: {e}")
        return False


def check_folder_contents(folder_path):
    """Check what video files are in the folder"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder does not exist: {folder_path}")
        return []
    
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(folder.glob(f"*{ext}"))
        video_files.extend(folder.glob(f"*{ext.upper()}"))
    
    print(f"📁 Found {len(video_files)} video files in {folder_path}:")
    for i, video_file in enumerate(video_files, 1):
        print(f"   {i}. {video_file.name}")
    
    return video_files


def main():
    """Main function"""
    
    # Default values - you can modify these
    folder_path = "test_videos/newsroom/2024"
    target_stage = "rendered"  # Options: discovered, prepped, transcribed, enriched, rendered
    
    # n8n webhook URL - you'll get this from your n8n workflow
    webhook_url = "http://localhost:5678/webhook/process-folder"
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    if len(sys.argv) > 2:
        target_stage = sys.argv[2]
    if len(sys.argv) > 3:
        webhook_url = sys.argv[3]
    
    print("🎯 Video Processing Pipeline - Folder Processing Test")
    print("=" * 60)
    
    # Check folder contents
    video_files = check_folder_contents(folder_path)
    
    if not video_files:
        print("\n❌ No video files found. Please add some videos to the folder first.")
        return
    
    print(f"\n🚀 Ready to process {len(video_files)} videos")
    print(f"   Each video will go through: Discovery → Media Prep → Transcription → Intelligence → Editorial → Web Artifacts")
    print()
    
    # Ask for confirmation
    response = input("Continue with processing? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Processing cancelled.")
        return
    
    # Trigger the workflow
    success = trigger_folder_processing(webhook_url, folder_path, target_stage)
    
    if success:
        print("\n🎉 Processing started!")
        print("   You can monitor progress in:")
        print("   - n8n interface: http://localhost:5678")
        print("   - API status: http://localhost:8000/status")
        print("   - API health: http://localhost:8000/health")
        print()
        print("   Expected outputs will be generated in:")
        print("   - transcripts/ (VTT and text files)")
        print("   - output/ (processed data)")
        print("   - web_artifacts/ (HTML pages and JSON)")
    else:
        print("\n❌ Failed to start processing. Check:")
        print("   - n8n is running: http://localhost:5678")
        print("   - API server is running: http://localhost:8000")
        print("   - Workflow is imported and active in n8n")


if __name__ == "__main__":
    main()