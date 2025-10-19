#!/usr/bin/env python3
"""
Speaker diarization using pyannote.audio
Outputs JSON with speaker segments
"""

import argparse
import json
import sys
import os
from pathlib import Path

def diarize_audio(audio_path, output_path=None, hf_token=None, num_speakers=None, device='cuda', merge_gap=2.0):
    """
    Diarize audio file and return speaker segments
    
    Args:
        audio_path: Path to audio/video file
        output_path: Path to save JSON output (optional)
        hf_token: Hugging Face API token
        num_speakers: Expected number of speakers (optional, helps accuracy)
        device: 'cuda' or 'cpu'
        merge_gap: Maximum gap to merge adjacent segments from same speaker
    
    Returns:
        dict: Segments with speaker labels and timestamps
    """
    try:
        from pyannote.audio import Pipeline
        import torch
    except ImportError as e:
        print(f"ERROR: Missing dependencies: {e}", file=sys.stderr)
        print("Run: pip install pyannote.audio torch", file=sys.stderr)
        sys.exit(1)
    
    # Check device availability
    if device == 'cuda' and not torch.cuda.is_available():
        print("WARNING: CUDA not available, falling back to CPU", file=sys.stderr)
        device = 'cpu'
    
    # Load pre-trained pipeline
    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        
        # Move to specified device
        if device == 'cuda':
            pipeline = pipeline.to(torch.device("cuda"))
        
    except Exception as e:
        print(f"ERROR: Failed to load pyannote pipeline: {e}", file=sys.stderr)
        print("Make sure you have accepted the model terms at:", file=sys.stderr)
        print("https://huggingface.co/pyannote/speaker-diarization", file=sys.stderr)
        sys.exit(1)
    
    # Run diarization
    try:
        if num_speakers:
            diarization = pipeline(audio_path, num_speakers=num_speakers)
        else:
            diarization = pipeline(audio_path)
    except Exception as e:
        print(f"ERROR: Diarization failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Convert to JSON-serializable format
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({
            "start": float(turn.start),
            "end": float(turn.end),
            "speaker": speaker,
            "duration": float(turn.end - turn.start)
        })
    
    # Merge adjacent segments from same speaker
    if merge_gap > 0:
        segments = merge_adjacent_segments(segments, merge_gap)
    
    # Sort by start time
    segments.sort(key=lambda x: x['start'])
    
    result = {
        "audio_file": str(audio_path),
        "num_speakers": len(set(seg["speaker"] for seg in segments)),
        "total_duration": max(seg["end"] for seg in segments) if segments else 0,
        "device_used": device,
        "segments": segments
    }
    
    # Save to file if specified
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
    
    return result


def merge_adjacent_segments(segments, max_gap=2.0):
    """Merge segments from same speaker if gap < max_gap seconds with optimization"""
    if not segments:
        return segments
    
    merged = []
    current = None
    merge_count = 0
    
    for seg in sorted(segments, key=lambda x: x['start']):
        if current is None:
            current = seg.copy()
        elif (seg['speaker'] == current['speaker'] and 
              (seg['start'] - current['end']) < max_gap):
            # Merge segments
            current['end'] = seg['end']
            current['duration'] = current['end'] - current['start']
            merge_count += 1
        else:
            merged.append(current)
            current = seg.copy()
    
    if current:
        merged.append(current)
    
    # Log merge statistics
    if merge_count > 0:
        print(f"✓ Merged {merge_count} adjacent segments", file=sys.stderr)
    
    return merged


def check_speaker_consistency(segments):
    """Check for speaker labeling consistency issues"""
    if not segments:
        return {"consistent": True, "issues": []}
    
    issues = []
    
    # Check for very short speaker turns (< 2 seconds) that might be errors
    short_turns = [seg for seg in segments if seg['duration'] < 2.0]
    if len(short_turns) > len(segments) * 0.2:
        issues.append(f"Many short speaker turns detected ({len(short_turns)}/{len(segments)})")
    
    # Check for speaker alternation patterns that seem unnatural
    speakers = [seg['speaker'] for seg in sorted(segments, key=lambda x: x['start'])]
    
    # Count rapid speaker changes (same speaker returns within 10 seconds)
    rapid_changes = 0
    for i in range(len(segments) - 2):
        current_seg = segments[i]
        next_next_seg = segments[i + 2] if i + 2 < len(segments) else None
        
        if (next_next_seg and 
            current_seg['speaker'] == next_next_seg['speaker'] and
            next_next_seg['start'] - current_seg['end'] < 10.0):
            rapid_changes += 1
    
    if rapid_changes > len(segments) * 0.1:
        issues.append(f"Frequent rapid speaker changes detected ({rapid_changes})")
    
    return {
        "consistent": len(issues) == 0,
        "issues": issues,
        "rapid_changes": rapid_changes,
        "short_turns": len(short_turns)
    }


def validate_diarization(segments):
    """Check diarization quality with enhanced validation"""
    issues = []
    warnings = []
    
    if len(segments) < 5:
        issues.append("Too few segments - possible diarization failure")
    
    # Check speaker balance
    speakers = {}
    for seg in segments:
        speakers[seg['speaker']] = speakers.get(seg['speaker'], 0) + seg['duration']
    
    if len(speakers) < 2:
        issues.append("Only one speaker detected")
    
    # Check reasonable speaker distribution
    total_time = sum(speakers.values())
    for speaker, time in speakers.items():
        ratio = time / total_time if total_time > 0 else 0
        if ratio < 0.05:
            issues.append(f"{speaker} speaks < 5% of time - possible error")
        elif ratio > 0.85:
            warnings.append(f"{speaker} dominates conversation ({ratio:.1%})")
    
    # Check for segment consistency
    segment_durations = [seg['duration'] for seg in segments]
    avg_duration = sum(segment_durations) / len(segment_durations) if segment_durations else 0
    
    very_short_segments = sum(1 for d in segment_durations if d < 1.0)
    if very_short_segments > len(segments) * 0.3:
        warnings.append(f"Many very short segments ({very_short_segments}/{len(segments)})")
    
    # Check for speaker labeling consistency
    speaker_labels = set(seg['speaker'] for seg in segments)
    if len(speaker_labels) > 10:
        warnings.append(f"Unusually high number of speakers detected: {len(speaker_labels)}")
    
    # Calculate quality score
    quality_score = 1.0
    quality_score -= len(issues) * 0.3  # Major penalty for issues
    quality_score -= len(warnings) * 0.1  # Minor penalty for warnings
    quality_score = max(0.0, min(1.0, quality_score))
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "quality_score": quality_score,
        "stats": {
            "num_segments": len(segments),
            "num_speakers": len(speakers),
            "speaker_distribution": speakers,
            "avg_segment_duration": avg_duration,
            "total_duration": total_time
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Diarize audio file')
    parser.add_argument('--audio', required=True, help='Path to audio/video file')
    parser.add_argument('--segments_out', required=True, help='Output JSON file path')
    parser.add_argument('--hf_token', help='Hugging Face token (or set HF_TOKEN env var)')
    parser.add_argument('--num_speakers', type=int, help='Expected number of speakers')
    parser.add_argument('--device', default='cuda', help='Device: cuda or cpu')
    parser.add_argument('--merge_gap', type=float, default=2.0, 
                       help='Max gap to merge segments (seconds)')
    
    args = parser.parse_args()
    
    # Get HF token from args or environment
    hf_token = args.hf_token or os.getenv('HF_TOKEN')
    if not hf_token:
        print("ERROR: Hugging Face token required. Set HF_TOKEN env var or use --hf_token", 
              file=sys.stderr)
        sys.exit(1)
    
    # Check input file exists
    if not os.path.exists(args.audio):
        print(f"ERROR: Audio file not found: {args.audio}", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory if needed
    output_dir = os.path.dirname(args.segments_out)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Run diarization
    try:
        result = diarize_audio(
            args.audio,
            args.segments_out,
            hf_token,
            args.num_speakers,
            args.device,
            args.merge_gap
        )
        
        # Validate results
        validation = validate_diarization(result['segments'])
        consistency = check_speaker_consistency(result['segments'])
        
        print(f"✓ Diarization complete: {len(result['segments'])} segments", file=sys.stderr)
        print(f"✓ Detected {result['num_speakers']} speakers", file=sys.stderr)
        print(f"✓ Total duration: {result['total_duration']:.1f}s", file=sys.stderr)
        print(f"✓ Device used: {result['device_used']}", file=sys.stderr)
        print(f"✓ Quality score: {validation['quality_score']:.2f}", file=sys.stderr)
        
        if validation['issues']:
            print("⚠ Quality issues detected:", file=sys.stderr)
            for issue in validation['issues']:
                print(f"  - {issue}", file=sys.stderr)
        
        if validation['warnings']:
            print("⚠ Quality warnings:", file=sys.stderr)
            for warning in validation['warnings']:
                print(f"  - {warning}", file=sys.stderr)
        
        if not consistency['consistent']:
            print("⚠ Speaker consistency issues:", file=sys.stderr)
            for issue in consistency['issues']:
                print(f"  - {issue}", file=sys.stderr)
        
        # Add validation and consistency data to result
        result['validation'] = validation
        result['consistency'] = consistency
        
        print(f"✓ Output saved to: {args.segments_out}", file=sys.stderr)
        
    except Exception as e:
        print(f"ERROR: Diarization failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()