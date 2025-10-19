#!/usr/bin/env python3
"""
Comprehensive test of all enrichment pipeline components
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))

def test_entity_extraction():
    """Test entity extraction with spaCy"""
    print("Testing Entity Extraction...")
    
    from extract_entities import extract_with_spacy
    
    # Test transcript
    transcript = """
    Welcome to Tech Talk. I'm John Smith, your host. Today we have Dr. Jane Doe, 
    Chief Technology Officer at Microsoft, and Professor Bob Wilson from MIT's 
    Computer Science Department discussing artificial intelligence and machine learning.
    """
    
    try:
        result = extract_with_spacy(transcript)
        
        assert 'candidates' in result
        assert 'topics' in result
        assert len(result['candidates']) > 0
        
        print(f"  ✓ Extracted {len(result['candidates'])} candidates")
        print(f"  ✓ Identified {len(result['topics'])} topics")
        
        return result
        
    except Exception as e:
        print(f"  ✗ Entity extraction failed: {e}")
        return None


def test_diarization_validation():
    """Test diarization validation functions"""
    print("Testing Diarization Validation...")
    
    from diarize import validate_diarization, merge_adjacent_segments
    
    # Test segments
    segments = [
        {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00", "duration": 10.0},
        {"start": 10.5, "end": 15.0, "speaker": "SPEAKER_00", "duration": 4.5},  # Should merge
        {"start": 15.0, "end": 25.0, "speaker": "SPEAKER_01", "duration": 10.0},
        {"start": 30.0, "end": 40.0, "speaker": "SPEAKER_00", "duration": 10.0},  # Gap too large
    ]
    
    try:
        # Test merging
        merged = merge_adjacent_segments(segments, max_gap=2.0)
        assert len(merged) == 3  # First two should merge
        print(f"  ✓ Segment merging: {len(segments)} → {len(merged)} segments")
        
        # Test validation
        validation = validate_diarization(segments)
        assert 'valid' in validation
        assert 'stats' in validation
        print(f"  ✓ Validation: {validation['stats']['num_speakers']} speakers detected")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Diarization validation failed: {e}")
        return False


def test_proficiency_scoring():
    """Test proficiency scoring"""
    print("Testing Proficiency Scoring...")
    
    from score_people import ProficiencyScorer
    
    # Mock enriched person
    person = {
        'name': 'Dr. Jane Doe',
        'job_title': 'Chief Technology Officer',
        'affiliation': 'Microsoft',
        'description': 'Technology executive and researcher',
        'wikidata_id': 'Q123456',
        'wikipedia_url': 'https://en.wikipedia.org/wiki/Jane_Doe',
        'knows_about': ['artificial intelligence', 'machine learning', 'technology']
    }
    
    topics = ['artificial intelligence', 'machine learning', 'technology', 'innovation']
    
    try:
        scorer = ProficiencyScorer()
        result = scorer.score_person(person, topics, [person])
        
        assert 'proficiencyScore' in result
        assert 'credibilityBadge' in result
        assert 'scoreBreakdown' in result
        assert 'reasoning' in result
        
        print(f"  ✓ Score: {result['proficiencyScore']:.3f}")
        print(f"  ✓ Badge: {result['credibilityBadge']}")
        print(f"  ✓ Reasoning: {result['reasoning']}")
        
        return result
        
    except Exception as e:
        print(f"  ✗ Proficiency scoring failed: {e}")
        return None


def test_file_io():
    """Test file I/O operations"""
    print("Testing File I/O...")
    
    test_data = {
        'test': True,
        'components': ['diarize', 'extract', 'disambiguate', 'score'],
        'timestamp': '2024-01-01T00:00:00Z'
    }
    
    try:
        # Test writing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f, indent=2)
            temp_path = f.name
        
        # Test reading
        with open(temp_path, 'r') as f:
            loaded_data = json.load(f)
        
        assert loaded_data == test_data
        print("  ✓ JSON write/read operations")
        
        # Cleanup
        os.unlink(temp_path)
        
        return True
        
    except Exception as e:
        print(f"  ✗ File I/O failed: {e}")
        return False


def test_error_handling():
    """Test error handling"""
    print("Testing Error Handling...")
    
    try:
        # Test missing file handling
        from extract_entities import extract_with_spacy
        
        # This should not crash
        result = extract_with_spacy("")
        assert result is not None
        print("  ✓ Empty input handling")
        
        # Test invalid data handling
        from diarize import validate_diarization
        
        validation = validate_diarization([])
        assert validation is not None
        print("  ✓ Empty segments handling")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error handling test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 50)
    print("AI Enrichment Pipeline Component Tests")
    print("=" * 50)
    
    tests = [
        test_file_io,
        test_diarization_validation,
        test_entity_extraction,
        test_proficiency_scoring,
        test_error_handling
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print("  ✓ PASSED\n")
            else:
                print("  ✗ FAILED\n")
        except Exception as e:
            print(f"  ✗ FAILED: {e}\n")
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All components are working correctly!")
        return 0
    else:
        print("⚠️  Some components need attention.")
        return 1


if __name__ == '__main__':
    sys.exit(main())