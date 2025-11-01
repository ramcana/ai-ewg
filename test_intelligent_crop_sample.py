"""
Test intelligent crop with existing clip
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.intelligent_crop import (
    IntelligentCropAnalyzer,
    IntelligentCropConfig,
    CropStrategy
)
from src.core.logging import get_logger

logger = get_logger('test.intelligent_crop_sample')


def test_with_existing_clip():
    """Test intelligent crop with existing 16x9 clip"""
    
    # Path to existing clip
    clip_path = Path(r"data\outputs\forum-daily\2025\TheNewsForum-ForumDailyNews-fd1314_10-27-25\clips\clip_50c37e6d5e62\16x9_clean.mp4")
    
    print("=" * 70)
    print("Testing Intelligent Crop with Existing Clip")
    print("=" * 70)
    print(f"\nClip: {clip_path}")
    
    # Check if file exists
    if not clip_path.exists():
        print(f"\n❌ ERROR: Clip not found at {clip_path}")
        print("\nPlease verify the path is correct.")
        return 1
    
    print(f"✅ Clip found: {clip_path.stat().st_size / (1024*1024):.2f} MB")
    
    # Get video duration using ffprobe
    import subprocess
    import json
    
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(clip_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            probe_data = json.loads(result.stdout)
            duration_seconds = float(probe_data['format']['duration'])
            print(f"✅ Duration: {duration_seconds:.2f} seconds")
        else:
            print("⚠️  Could not determine duration")
            duration_seconds = 60  # Assume 60 seconds
    except Exception as e:
        print(f"⚠️  Could not probe video: {e}")
        duration_seconds = 60
    
    # Test different strategies
    strategies = [
        ("Center Crop", CropStrategy.CENTER, False, False),
        ("Face Tracking", CropStrategy.FACE_TRACKING, True, False),
        ("Motion Aware", CropStrategy.MOTION_AWARE, False, True),
        ("Hybrid", CropStrategy.HYBRID, True, True),
    ]
    
    for strategy_name, strategy, enable_face, enable_motion in strategies:
        print("\n" + "-" * 70)
        print(f"Testing: {strategy_name}")
        print("-" * 70)
        
        try:
            # Create configuration
            config = IntelligentCropConfig(
                strategy=strategy,
                enable_face_detection=enable_face,
                enable_motion_detection=enable_motion,
                smooth_transitions=True,
                transition_smoothness=0.3,
                max_analysis_fps=5,  # Low FPS for faster testing
                use_gpu=True
            )
            
            # Initialize analyzer
            analyzer = IntelligentCropAnalyzer(config)
            
            # Analyze first 10 seconds (or full duration if shorter)
            analysis_duration = min(10000, int(duration_seconds * 1000))
            
            print(f"Analyzing {analysis_duration/1000:.1f} seconds...")
            
            # Analyze for 9:16 vertical crop (typical for social media)
            crop_regions = analyzer.analyze_video(
                video_path=clip_path,
                start_ms=0,
                end_ms=analysis_duration,
                target_width=1080,
                target_height=1920
            )
            
            print(f"✅ Analysis complete: {len(crop_regions)} crop regions generated")
            
            if crop_regions:
                # Show first few regions
                print("\nCrop Regions:")
                for i, region in enumerate(crop_regions[:5]):
                    print(f"  [{i+1}] Time: {region.timestamp_ms/1000:.2f}s")
                    print(f"      Position: ({region.x}, {region.y})")
                    print(f"      Size: {region.width}x{region.height}")
                    print(f"      Strategy: {region.strategy_used}")
                    print(f"      Confidence: {region.confidence:.2f}")
                
                if len(crop_regions) > 5:
                    print(f"  ... and {len(crop_regions) - 5} more regions")
                
                # Show statistics
                strategies_used = {}
                for region in crop_regions:
                    strategies_used[region.strategy_used] = strategies_used.get(region.strategy_used, 0) + 1
                
                print("\nStrategy Distribution:")
                for strat, count in strategies_used.items():
                    percentage = (count / len(crop_regions)) * 100
                    print(f"  {strat}: {count} regions ({percentage:.1f}%)")
                
                # Calculate average confidence
                avg_confidence = sum(r.confidence for r in crop_regions) / len(crop_regions)
                print(f"\nAverage Confidence: {avg_confidence:.2f}")
            else:
                print("⚠️  No crop regions generated")
        
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(test_with_existing_clip())
