#!/usr/bin/env python3
"""
Example test script for Intelligence Chain V2

Demonstrates:
- Typed model usage
- Cache behavior
- Quality gates
- Explainability payloads
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.intelligence_models import (
    DiarizationResult, DiarizationSegment,
    EntitiesResult, EntityMention,
    ChainContext
)
from core.intelligence_cache import IntelligenceCache, CacheKey
from core.intelligence_quality import QualityGateManager


def example_typed_models():
    """Example: Using typed pydantic models"""
    print("\n=== Example 1: Typed Models ===\n")
    
    # Create a diarization result
    result = DiarizationResult(
        audio_file="test.mp4",
        num_speakers=2,
        total_duration=120.5,
        device_used="cuda",
        segments=[
            DiarizationSegment(
                start=0.0,
                end=5.2,
                speaker="SPEAKER_00",
                duration=5.2
            ),
            DiarizationSegment(
                start=5.5,
                end=12.3,
                speaker="SPEAKER_01",
                duration=6.8
            )
        ]
    )
    
    print(f"Schema version: {result.schema_version}")
    print(f"Speakers: {result.num_speakers}")
    print(f"Segments: {len(result.segments)}")
    print(f"First segment: {result.segments[0].speaker} ({result.segments[0].duration}s)")
    
    # Serialize to JSON
    json_str = result.json(indent=2)
    print(f"\nJSON output (first 200 chars):\n{json_str[:200]}...")
    
    # Deserialize back
    result_copy = DiarizationResult.parse_raw(json_str)
    print(f"\nDeserialized: {result_copy.num_speakers} speakers")


def example_caching():
    """Example: Content-addressed caching"""
    print("\n=== Example 2: Caching ===\n")
    
    # Initialize cache
    cache = IntelligenceCache(Path("data/cache_example"))
    
    # Create cache key
    cache_key = CacheKey(
        step_name="diarization",
        video_hash="abc123def456" * 4,  # 64 chars
        config_hash="789ghi012jkl" * 4,
        step_version="1.0.0"
    )
    
    print(f"Cache key: {cache_key.to_string()}")
    print(f"Cache hash: {cache_key.to_hash()[:16]}...")
    
    # Create test result
    result = DiarizationResult(
        audio_file="test.mp4",
        num_speakers=2,
        total_duration=120.5,
        device_used="cuda",
        segments=[
            DiarizationSegment(start=0.0, end=5.2, speaker="SPEAKER_00", duration=5.2)
        ]
    )
    
    # Store in cache
    cache.set_cache(cache_key, result, duration_ms=45230.0)
    print(f"\n✓ Cached result")
    
    # Retrieve from cache
    cached_result = cache.get_cache(cache_key, DiarizationResult)
    if cached_result:
        print(f"✓ Retrieved from cache: {cached_result.num_speakers} speakers")
    
    # Check cache stats
    stats = cache.get_cache_stats()
    print(f"\nCache stats:")
    print(f"  Total files: {stats['total_files']}")
    print(f"  Total size: {stats['total_size_bytes']} bytes")
    
    # Cleanup
    cache.clear_all_cache()
    print(f"\n✓ Cleared cache")


def example_quality_gates():
    """Example: Quality gate validation"""
    print("\n=== Example 3: Quality Gates ===\n")
    
    quality_manager = QualityGateManager()
    
    # Test 1: Good diarization result
    good_result = DiarizationResult(
        audio_file="test.mp4",
        num_speakers=2,
        total_duration=120.5,
        device_used="cuda",
        segments=[
            DiarizationSegment(start=i*10.0, end=(i+1)*10.0, speaker=f"SPEAKER_{i%2:02d}", duration=10.0)
            for i in range(12)
        ],
        validation={'valid': True, 'quality_score': 0.95, 'issues': []},
        consistency={'consistent': True, 'issues': []}
    )
    
    passed, quality_level, warnings = quality_manager.check_step('diarization', good_result)
    print(f"Good result: passed={passed}, quality={quality_level.value}, warnings={len(warnings)}")
    
    # Test 2: Degraded diarization result
    degraded_result = DiarizationResult(
        audio_file="test.mp4",
        num_speakers=1,  # Only one speaker
        total_duration=120.5,
        device_used="cuda",
        segments=[
            DiarizationSegment(start=0.0, end=1.0, speaker="SPEAKER_00", duration=1.0),
            DiarizationSegment(start=1.0, end=2.0, speaker="SPEAKER_00", duration=1.0)
        ],  # Too few segments
        validation={'valid': False, 'quality_score': 0.4, 'issues': ['Low quality']},
        consistency={'consistent': False, 'issues': ['Inconsistent']}
    )
    
    passed, quality_level, warnings = quality_manager.check_step('diarization', degraded_result)
    print(f"\nDegraded result: passed={passed}, quality={quality_level.value}, warnings={len(warnings)}")
    for warning in warnings:
        print(f"  [{warning.severity}] {warning.message}")
    
    # Get fallback strategy
    strategy = quality_manager.get_fallback_strategy('diarization', quality_level)
    if strategy:
        print(f"\nFallback strategy: {strategy}")


def example_explainability():
    """Example: Explainability payload structure"""
    print("\n=== Example 4: Explainability ===\n")
    
    # Example disambiguation decision
    decision = {
        'name': 'Jane Smith',
        'confidence': 0.87,
        'authority_level': 'high',
        'decision_rule': 'Overlap(name) + Context(topic)=0.78 > 0.65',
        'candidates_considered': 3,
        'evidence': [
            {
                'source': 'NER',
                'text': 'Jane Smith, economist at Bank of Canada',
                'timestamp_range': (45.2, 52.8),
                'score': 0.9
            }
        ]
    }
    
    print("Disambiguation decision:")
    print(f"  Name: {decision['name']}")
    print(f"  Confidence: {decision['confidence']:.2f}")
    print(f"  Authority: {decision['authority_level']}")
    print(f"  Rule: {decision['decision_rule']}")
    print(f"  Candidates: {decision['candidates_considered']}")
    print(f"  Evidence: {len(decision['evidence'])} items")
    
    # Example proficiency score breakdown
    score_breakdown = {
        'name': 'Jane Smith',
        'proficiencyScore': 0.82,
        'credibilityBadge': 'Verified Expert',
        'breakdown': {
            'roleMatch': 0.200,
            'authorityDomain': 0.180,
            'knowledgeBase': 0.150,
            'publications': 0.080,
            'recency': 0.090,
            'journalisticRelevance': 0.090,
            'authorityVerification': 0.100,
            'ambiguityPenalty': -0.070
        },
        'reasoning': 'Verified through authoritative sources; high credibility score'
    }
    
    print("\nProficiency score breakdown:")
    print(f"  Name: {score_breakdown['name']}")
    print(f"  Score: {score_breakdown['proficiencyScore']:.2f}")
    print(f"  Badge: {score_breakdown['credibilityBadge']}")
    print(f"  Breakdown:")
    for criterion, score in score_breakdown['breakdown'].items():
        print(f"    {criterion}: {score:.3f}")
    print(f"  Reasoning: {score_breakdown['reasoning']}")


def example_chain_context():
    """Example: Chain execution context"""
    print("\n=== Example 5: Chain Context ===\n")
    
    context = ChainContext(
        job_id="episode-123-abc",
        episode_id="show-s01e05",
        video_hash="abc123def456" * 4,
        config_hash="789ghi012jkl" * 4,
        paths={
            'audio': '/path/to/audio.mp4',
            'transcript': '/path/to/transcript.txt'
        },
        force_rerun=False,
        start_from_step=None,
        stop_at_step=None
    )
    
    print(f"Job ID: {context.job_id}")
    print(f"Episode ID: {context.episode_id}")
    print(f"Video hash: {context.video_hash[:16]}...")
    print(f"Config hash: {context.config_hash[:16]}...")
    print(f"Force rerun: {context.force_rerun}")
    print(f"Paths: {list(context.paths.keys())}")
    
    # Context is immutable
    try:
        context.force_rerun = True  # This will fail
    except Exception as e:
        print(f"\n✓ Context is immutable: {type(e).__name__}")


def main():
    """Run all examples"""
    print("=" * 60)
    print("Intelligence Chain V2 - Examples")
    print("=" * 60)
    
    try:
        example_typed_models()
        example_caching()
        example_quality_gates()
        example_explainability()
        example_chain_context()
        
        print("\n" + "=" * 60)
        print("✓ All examples completed successfully")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Example failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
