#!/usr/bin/env python3
"""
CLI tool for running intelligence chain with caching and quality gates

Supports:
- --force: Force rerun (ignore cache)
- --from-step: Start from specific step
- --until-step: Stop at specific step
- --clear-cache: Clear cache before running
- --show-cache-stats: Show cache statistics
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import ConfigurationManager
from core.intelligence_chain_v2 import IntelligenceChainOrchestratorV2
from core.models import EpisodeObject, EpisodeMetadata, SourceInfo, MediaInfo, ProcessingStage
from datetime import datetime


def create_test_episode(video_path: str) -> EpisodeObject:
    """Create a test episode object"""
    path = Path(video_path)
    
    return EpisodeObject(
        episode_id=f"test-{path.stem}",
        content_hash="test-hash",
        source=SourceInfo(
            path=str(path),
            file_size=path.stat().st_size if path.exists() else 0,
            last_modified=datetime.now()
        ),
        media=MediaInfo(),
        metadata=EpisodeMetadata(
            show_name="Test Show",
            show_slug="test-show"
        ),
        processing_stage=ProcessingStage.TRANSCRIBED
    )


async def main():
    parser = argparse.ArgumentParser(
        description='Run intelligence chain with caching and quality gates'
    )
    
    # Input files
    parser.add_argument('--audio', required=True, help='Path to audio/video file')
    parser.add_argument('--transcript', required=True, help='Path to transcript text file')
    
    # Execution control
    parser.add_argument('--force', action='store_true', help='Force rerun (ignore cache)')
    parser.add_argument('--from-step', help='Start from this step (diarization, extract_entities, disambiguate, score_people)')
    parser.add_argument('--until-step', help='Stop at this step')
    
    # Cache management
    parser.add_argument('--clear-cache', action='store_true', help='Clear cache before running')
    parser.add_argument('--clear-step-cache', help='Clear cache for specific step')
    parser.add_argument('--show-cache-stats', action='store_true', help='Show cache statistics')
    
    # Configuration
    parser.add_argument('--config', help='Path to config YAML file')
    
    # Output
    parser.add_argument('--output-dir', default='output', help='Output directory for results')
    
    args = parser.parse_args()
    
    # Load configuration
    config_manager = ConfigurationManager(args.config)
    config = config_manager.load_config()
    
    # Create orchestrator
    orchestrator = IntelligenceChainOrchestratorV2(config)
    
    # Show cache stats if requested
    if args.show_cache_stats:
        stats = orchestrator.get_cache_stats()
        print("\n=== Cache Statistics ===")
        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size_bytes'] / 1024 / 1024:.2f} MB")
        print("\nPer-step breakdown:")
        for step_name, step_stats in stats['steps'].items():
            print(f"  {step_name}: {step_stats['files']} files, {step_stats['size_bytes'] / 1024:.2f} KB")
        print()
    
    # Clear cache if requested
    if args.clear_cache:
        count = orchestrator.clear_cache()
        print(f"Cleared {count} cache files\n")
    
    if args.clear_step_cache:
        count = orchestrator.clear_cache(args.clear_step_cache)
        print(f"Cleared {count} cache files for step: {args.clear_step_cache}\n")
    
    # Check input files
    audio_path = Path(args.audio)
    transcript_path = Path(args.transcript)
    
    if not audio_path.exists():
        print(f"ERROR: Audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)
    
    if not transcript_path.exists():
        print(f"ERROR: Transcript file not found: {transcript_path}", file=sys.stderr)
        sys.exit(1)
    
    # Read transcript
    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript_text = f.read()
    
    # Create episode
    episode = create_test_episode(str(audio_path))
    
    # Run intelligence chain
    print(f"\n=== Running Intelligence Chain V2 ===")
    print(f"Audio: {audio_path}")
    print(f"Transcript: {transcript_path}")
    print(f"Force rerun: {args.force}")
    if args.from_step:
        print(f"Start from: {args.from_step}")
    if args.until_step:
        print(f"Stop at: {args.until_step}")
    print()
    
    result = await orchestrator.process_episode(
        episode=episode,
        audio_path=str(audio_path),
        transcript_text=transcript_text,
        force_rerun=args.force,
        start_from_step=args.from_step,
        stop_at_step=args.until_step
    )
    
    # Print results
    print("\n=== Results ===")
    print(f"Success: {result.success}")
    print(f"Job ID: {result.metadata.job_id}")
    print(f"Duration: {result.metadata.total_duration_ms:.0f}ms")
    print(f"Cache hits: {result.metadata.cache_hits}")
    print(f"Cache misses: {result.metadata.cache_misses}")
    
    if result.error:
        print(f"\nError: {result.error}")
        if result.error_step:
            print(f"Failed at step: {result.error_step}")
    
    # Print step summary
    print("\n=== Steps ===")
    for step in result.metadata.steps_completed:
        print(f"  ✓ {step}")
    for step in result.metadata.steps_cached:
        print(f"  ⚡ {step} (cached)")
    for step in result.metadata.steps_failed:
        print(f"  ✗ {step} (failed)")
    
    # Print warnings
    if result.metadata.warnings:
        print("\n=== Warnings ===")
        for warning in result.metadata.warnings:
            print(f"  [{warning.severity}] {warning.step_name}: {warning.message}")
    
    # Print stage results
    if result.diarization:
        print(f"\nDiarization: {result.diarization.num_speakers} speakers, {len(result.diarization.segments)} segments")
    
    if result.entities:
        print(f"Entities: {len(result.entities.candidates)} candidates, {len(result.entities.topics)} topics")
    
    if result.resolution:
        print(f"Resolution: {len(result.resolution.enriched_people)} enriched")
    
    if result.proficiency:
        print(f"Proficiency: {len(result.proficiency.scored_people)} scored")
    
    # Save results to output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = output_dir / f"{result.metadata.job_id}.result.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(result.json(indent=2))
    
    print(f"\nResults saved to: {result_file}")
    print(f"Metadata: data/meta/{result.metadata.job_id}.json")
    print(f"Explainability: data/meta/{result.metadata.job_id}.explain.json")
    print(f"Quality report: data/meta/{result.metadata.job_id}.quality.json")
    
    sys.exit(0 if result.success else 1)


if __name__ == '__main__':
    asyncio.run(main())
