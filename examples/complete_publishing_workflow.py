#!/usr/bin/env python3
"""
Complete Publishing Workflow Example

Demonstrates the end-to-end content publishing workflow using the
integrated Content Publishing Platform.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.main_integration import (
    ContentPublishingPlatform, 
    create_content_publishing_platform,
    quick_publish,
    setup_new_platform,
    get_platform_info
)
from core.publishing_config import Environment, FeatureFlag


def progress_callback(message: str, progress: float, metadata: dict):
    """Progress callback for workflow monitoring"""
    print(f"[{progress*100:5.1f}%] {message}")
    if metadata:
        print(f"         Metadata: {json.dumps(metadata, indent=2)}")


def main():
    """Main example execution"""
    print("Content Publishing Platform - Complete Workflow Example")
    print("=" * 60)
    
    # Get platform information
    platform_info = get_platform_info()
    print(f"Platform: {platform_info['name']} v{platform_info['version']}")
    print(f"Description: {platform_info['description']}")
    print()
    
    # Set up configuration directory
    config_dir = "config"
    
    try:
        # Create and initialize platform
        print("1. Initializing Content Publishing Platform...")
        platform = create_content_publishing_platform(
            config_dir=config_dir,
            environment=Environment.DEVELOPMENT,
            auto_setup=True
        )
        
        # Add progress callback
        platform.add_progress_callback(progress_callback)
        
        print("   ✓ Platform initialized successfully")
        print()
        
        # Validate system
        print("2. Validating system configuration...")
        validation = platform.validate_system()
        
        if validation.is_valid:
            print("   ✓ System validation passed")
        else:
            print(f"   ⚠ System validation found {len(validation.errors)} errors:")
            for error in validation.errors[:5]:  # Show first 5 errors
                print(f"     - {error.message}")
            if len(validation.errors) > 5:
                print(f"     ... and {len(validation.errors) - 5} more errors")
        
        if validation.warnings:
            print(f"   ⚠ {len(validation.warnings)} warnings found:")
            for warning in validation.warnings[:3]:  # Show first 3 warnings
                print(f"     - {warning.message}")
        
        print()
        
        # Get system status
        print("3. Checking system status...")
        status = platform.get_system_status()
        
        print(f"   Environment: {status['platform_info']['environment']}")
        print(f"   System Health: {status['system_health']['overall_status']}")
        print(f"   Configuration Valid: {status['configuration']['valid']}")
        print(f"   Active Workflows: {status['active_workflows']}")
        
        # Show enabled features
        enabled_features = [
            flag for flag, enabled in status['configuration']['feature_flags'].items() 
            if enabled
        ]
        print(f"   Enabled Features: {', '.join(enabled_features) if enabled_features else 'None'}")
        print()
        
        # Check for manifest file
        manifest_path = "data/publish_manifest.json"
        if not Path(manifest_path).exists():
            print(f"4. Creating example manifest at {manifest_path}...")
            create_example_manifest(manifest_path)
            print("   ✓ Example manifest created")
        else:
            print(f"4. Using existing manifest at {manifest_path}")
        
        print()
        
        # Get content statistics
        print("5. Analyzing content...")
        try:
            content_stats = platform.get_content_statistics()
            if 'error' not in content_stats:
                print(f"   Episodes: {content_stats.get('total_episodes', 0)}")
                print(f"   Series: {content_stats.get('total_series', 0)}")
                print(f"   Hosts: {content_stats.get('total_hosts', 0)}")
                print(f"   Build ID: {content_stats.get('build_id', 'Unknown')}")
            else:
                print(f"   ⚠ Content analysis failed: {content_stats['error']}")
        except Exception as e:
            print(f"   ⚠ Content analysis failed: {str(e)}")
        
        print()
        
        # Execute publishing workflow (dry run mode for example)
        print("6. Executing publishing workflow...")
        print("   Note: This is a demonstration - actual deployment disabled")
        
        # In a real scenario, you would call:
        # report = platform.publish_content(manifest_path)
        
        # For this example, we'll simulate the workflow
        print("   [Simulated] Workflow would execute the following phases:")
        print("   - Content loading and validation")
        print("   - Web content generation")
        print("   - Social media package creation")
        print("   - Staging deployment")
        print("   - Validation gates")
        print("   - Production deployment")
        print("   - Platform integration")
        print("   ✓ Workflow simulation complete")
        print()
        
        # Show workflow history
        print("7. Workflow history...")
        history = platform.get_workflow_history(5)
        if history:
            print(f"   Found {len(history)} recent workflows:")
            for i, report in enumerate(history[:3], 1):
                status_icon = "✓" if report.workflow_result.status.value == "completed" else "✗"
                print(f"   {i}. {status_icon} {report.workflow_result.workflow_id} - {report.workflow_result.status.value}")
        else:
            print("   No workflow history found")
        
        print()
        
        # Performance metrics
        print("8. Performance metrics...")
        try:
            metrics = platform.get_performance_metrics()
            if 'message' not in metrics:
                print(f"   Recent workflows: {metrics.get('recent_workflows', 0)}")
                print(f"   Success rate: {metrics.get('success_rate', 0)*100:.1f}%")
                print(f"   Avg processing time: {metrics.get('average_processing_time_seconds', 0):.1f}s")
            else:
                print(f"   {metrics['message']}")
        except Exception as e:
            print(f"   ⚠ Metrics unavailable: {str(e)}")
        
        print()
        print("Example completed successfully!")
        
    except Exception as e:
        print(f"❌ Example failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


def create_example_manifest(manifest_path: str):
    """Create an example publish manifest for demonstration"""
    manifest_dir = Path(manifest_path).parent
    manifest_dir.mkdir(parents=True, exist_ok=True)
    
    # Create example manifest
    example_manifest = {
        "manifest_version": "2.0",
        "build_id": f"example_build_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.now().isoformat(),
        "episodes": [
            {
                "episode_id": "example_episode_001",
                "title": "Introduction to Content Publishing",
                "description": "An overview of automated content publishing workflows and best practices.",
                "upload_date": datetime.now().isoformat(),
                "duration_seconds": 1800,
                "series_id": "example_series",
                "host_ids": ["example_host"],
                "tags": ["publishing", "automation", "content"],
                "thumbnail_url": "https://example.com/thumbnails/episode_001.jpg",
                "content_url": "https://example.com/videos/episode_001.mp4",
                "transcript_path": "data/transcripts/episode_001.vtt",
                "social_links": {}
            }
        ],
        "series": [
            {
                "series_id": "example_series",
                "title": "Content Publishing Masterclass",
                "description": "Learn how to build and deploy automated content publishing systems.",
                "slug": "content-publishing-masterclass",
                "primary_host": {
                    "person_id": "example_host",
                    "name": "Alex Publisher",
                    "slug": "alex-publisher"
                },
                "artwork_url": "https://example.com/artwork/series.jpg",
                "topics": ["publishing", "automation", "web development"]
            }
        ],
        "hosts": [
            {
                "person_id": "example_host",
                "name": "Alex Publisher",
                "slug": "alex-publisher",
                "bio": "Expert in automated content publishing and web development.",
                "headshot_url": "https://example.com/headshots/alex.jpg",
                "same_as_links": ["https://example.com/alex"],
                "affiliation": "Content Publishing Platform",
                "shows": ["example_series"]
            }
        ],
        "paths": {
            "public_root": "data/public",
            "meta_root": "data/meta",
            "transcripts_root": "data/transcripts",
            "social_root": "data/social"
        }
    }
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(example_manifest, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())