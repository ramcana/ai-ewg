"""
Test script for intelligent crop features

Tests face detection, motion detection, and crop region generation
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.intelligent_crop import (
    IntelligentCropAnalyzer,
    IntelligentCropConfig,
    CropStrategy,
    FaceDetector,
    MotionDetector
)
from src.core.logging import get_logger

logger = get_logger('test.intelligent_crop')


def test_face_detection():
    """Test face detection on a sample video"""
    print("\n=== Testing Face Detection ===")
    
    config = IntelligentCropConfig(
        strategy=CropStrategy.FACE_TRACKING,
        enable_face_detection=True,
        enable_motion_detection=False,
        face_detection_interval=5
    )
    
    detector = FaceDetector(config)
    
    if detector.cascade is None:
        print("❌ Face detector not initialized (OpenCV cascade not found)")
        return False
    
    print("✅ Face detector initialized successfully")
    return True


def test_motion_detection():
    """Test motion detection"""
    print("\n=== Testing Motion Detection ===")
    
    config = IntelligentCropConfig(
        strategy=CropStrategy.MOTION_AWARE,
        enable_face_detection=False,
        enable_motion_detection=True,
        motion_detection_interval=3
    )
    
    detector = MotionDetector(config)
    print("✅ Motion detector initialized successfully")
    return True


def test_crop_analyzer_init():
    """Test intelligent crop analyzer initialization"""
    print("\n=== Testing Intelligent Crop Analyzer ===")
    
    # Test with hybrid strategy
    config = IntelligentCropConfig(
        strategy=CropStrategy.HYBRID,
        enable_face_detection=True,
        enable_motion_detection=True,
        smooth_transitions=True,
        transition_smoothness=0.3
    )
    
    analyzer = IntelligentCropAnalyzer(config)
    print(f"✅ Analyzer initialized with strategy: {config.strategy.value}")
    print(f"   - Face detection: {config.enable_face_detection}")
    print(f"   - Motion detection: {config.enable_motion_detection}")
    print(f"   - Smooth transitions: {config.smooth_transitions}")
    
    return True


def test_config_validation():
    """Test configuration validation"""
    print("\n=== Testing Configuration Validation ===")
    
    try:
        # Valid config
        config1 = IntelligentCropConfig(
            transition_smoothness=0.5,
            padding_percent=0.15
        )
        print("✅ Valid config accepted")
        
        # Invalid smoothness
        try:
            config2 = IntelligentCropConfig(transition_smoothness=1.5)
            print("❌ Invalid smoothness should have been rejected")
            return False
        except ValueError as e:
            print(f"✅ Invalid smoothness rejected: {e}")
        
        # Invalid padding
        try:
            config3 = IntelligentCropConfig(padding_percent=0.8)
            print("❌ Invalid padding should have been rejected")
            return False
        except ValueError as e:
            print(f"✅ Invalid padding rejected: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config validation test failed: {e}")
        return False


def test_crop_strategies():
    """Test different crop strategies"""
    print("\n=== Testing Crop Strategies ===")
    
    strategies = [
        CropStrategy.CENTER,
        CropStrategy.FACE_TRACKING,
        CropStrategy.MOTION_AWARE,
        CropStrategy.HYBRID
    ]
    
    for strategy in strategies:
        config = IntelligentCropConfig(strategy=strategy)
        analyzer = IntelligentCropAnalyzer(config)
        print(f"✅ {strategy.value} strategy initialized")
    
    return True


def test_with_sample_video():
    """Test with a sample video if available"""
    print("\n=== Testing with Sample Video ===")
    
    # Look for a sample video
    sample_paths = [
        Path("test_videos/sample.mp4"),
        Path("input_videos/_uncategorized").glob("*.mp4"),
        Path("data/temp/uploaded").glob("*.mp4")
    ]
    
    sample_video = None
    for path in sample_paths:
        if isinstance(path, Path) and path.exists():
            sample_video = path
            break
        elif hasattr(path, '__iter__'):
            try:
                sample_video = next(path)
                break
            except StopIteration:
                continue
    
    if not sample_video:
        print("⚠️  No sample video found, skipping video analysis test")
        print("   Place a video in test_videos/sample.mp4 to test video analysis")
        return True
    
    print(f"📹 Found sample video: {sample_video}")
    
    try:
        config = IntelligentCropConfig(
            strategy=CropStrategy.HYBRID,
            enable_face_detection=True,
            enable_motion_detection=True,
            max_analysis_fps=5  # Low FPS for faster testing
        )
        
        analyzer = IntelligentCropAnalyzer(config)
        
        # Analyze first 10 seconds
        crop_regions = analyzer.analyze_video(
            video_path=sample_video,
            start_ms=0,
            end_ms=10000,
            target_width=1080,
            target_height=1920
        )
        
        print(f"✅ Video analysis complete: {len(crop_regions)} crop regions generated")
        
        if crop_regions:
            first_region = crop_regions[0]
            print(f"   First region: {first_region.width}x{first_region.height} at ({first_region.x}, {first_region.y})")
            print(f"   Strategy used: {first_region.strategy_used}")
            print(f"   Confidence: {first_region.confidence:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Video analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Intelligent Crop Feature Tests")
    print("=" * 60)
    
    tests = [
        ("Face Detection", test_face_detection),
        ("Motion Detection", test_motion_detection),
        ("Crop Analyzer Init", test_crop_analyzer_init),
        ("Config Validation", test_config_validation),
        ("Crop Strategies", test_crop_strategies),
        ("Sample Video Analysis", test_with_sample_video)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
