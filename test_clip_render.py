"""Test clip rendering to see actual error"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.clip_export import ClipExportSystem, ClipSpecification, ClipVariantSpec
from core.models import TranscriptionResult

async def test_render():
    # Episode details
    episode_id = 'temp-uploaded-fd1314_10-27-25'
    source_path = r'D:\n8n\ai-ewg\data\temp\uploaded\FD1314_10-27-25.mp4'
    
    # Check if source exists
    if not Path(source_path).exists():
        print(f"❌ Source file not found: {source_path}")
        return
    
    print(f"✓ Source file exists: {source_path}")
    print(f"✓ File size: {Path(source_path).stat().st_size / (1024*1024):.1f} MB")
    
    # Create a simple clip spec (first 30 seconds)
    clip_spec = ClipSpecification(
        clip_id="test_clip",
        episode_id=episode_id,
        start_ms=0,
        end_ms=30000,  # 30 seconds
        score=0.8,
        sentences=[]
    )
    
    # Create variant spec
    variant_spec = ClipVariantSpec(
        variant="clean",
        aspect_ratio="16x9",
        output_path="temp/test_clip_16x9_clean.mp4"
    )
    
    print(f"\nAttempting to render test clip (0-30s)...")
    print(f"Output: {variant_spec.output_path}")
    
    # Initialize export system
    try:
        export_system = ClipExportSystem()
        print("✓ ClipExportSystem initialized")
    except Exception as e:
        print(f"❌ Failed to initialize ClipExportSystem: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Try to render
    try:
        assets = export_system.render_clip(
            clip_spec=clip_spec,
            source_path=source_path,
            transcript=None  # No subtitles for this test
        )
        print(f"✓ Clip rendered successfully!")
        print(f"✓ Assets created: {len(assets)}")
        for asset in assets:
            print(f"  - {asset.path} ({asset.variant}, {asset.aspect_ratio})")
    except Exception as e:
        print(f"\n❌ Rendering failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_render())
