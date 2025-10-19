#!/usr/bin/env python3
"""
Test the complete enrichment pipeline with sample data
"""

import json
import tempfile
import os
from pathlib import Path

def create_sample_transcript():
    """Create a sample transcript for testing"""
    return """
Good evening, I'm your host Alex Johnson. Tonight we're discussing the economic outlook with our special guest, Dr. Sarah Martinez, Chief Economist at the Bank of Canada.

Dr. Martinez, thanks for joining us.

Thank you, Alex. It's great to be here.

Let's talk about inflation. What's your assessment of the current situation?

Well, as I mentioned in my recent paper on monetary policy, we're seeing interesting dynamics. Inflation has been moderating, but we need to remain vigilant. The Bank of Canada is closely monitoring several indicators.

You've been at the Bank for what, ten years now?

That's right. I joined in 2015 as a senior analyst and became Chief Economist in 2020.

Before we wrap up, any final thoughts?

Just that monetary policy decisions are complex, and we're committed to maintaining price stability for all Canadians.

Thank you, Dr. Martinez, for those insights.
"""

def test_entity_extraction():
    """Test entity extraction"""
    print("\n" + "="*50)
    print("TEST 1: Entity Extraction (spaCy)")
    print("="*50)
    
    from extract_entities import extract_with_spacy
    
    transcript = create_sample_transcript()
    
    try:
        result = extract_with_spacy(transcript)
        
        print(f"✓ Candidates extracted: {len(result['candidates'])}")
        print(f"✓ Topics identified: {len(result['topics'])}")
        
        for candidate in result['candidates']:
            print(f"\n  Name: {candidate['name']}")
            print(f"  Role: {candidate.get('role_guess', 'N/A')}")
            print(f"  Org: {candidate.get('org_guess', 'N/A')}")
            print(f"  Confidence: {candidate.get('confidence', 0):.2f}")
        
        return result
        
    except Exception as e:
        print(f"✗ Entity extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_disambiguation(candidates_data):
    """Test disambiguation (with mock data to avoid API calls)"""
    print("\n" + "="*50)
    print("TEST 2: Disambiguation (Mock)")
    print("="*50)
    
    # Mock enriched data based on candidates
    enriched_people = []
    
    for candidate in candidates_data['candidates'][:2]:  # Test first 2
        mock_enriched = {
            "wikidata_id": "Q12345",
            "name": candidate['name'],
            "description": "Canadian economist",
            "job_title": candidate.get('role_guess', 'Economist'),
            "affiliation": candidate.get('org_guess', 'Bank of Canada'),
            "knows_about": ["monetary policy", "inflation", "economics"],
            "wikipedia_url": "https://en.wikipedia.org/wiki/Example",
            "same_as": [
                "https://www.wikidata.org/wiki/Q12345",
                "https://en.wikipedia.org/wiki/Example"
            ],
            "confidence": 0.85,
            "original_name": candidate['name']
        }
        enriched_people.append(mock_enriched)
    
    result = {
        "enriched_people": enriched_people,
        "original_candidates": candidates_data['candidates'],
        "topics": candidates_data.get('topics', []),
        "summary": {
            "total_candidates": len(candidates_data['candidates']),
            "enriched_count": len(enriched_people),
            "success_rate": len(enriched_people) / len(candidates_data['candidates']) if candidates_data['candidates'] else 0
        }
    }
    
    print(f"✓ Enriched: {len(enriched_people)} people")
    print(f"✓ Success rate: {result['summary']['success_rate']:.1%}")
    
    return result

def test_scoring(enriched_data):
    """Test proficiency scoring"""
    print("\n" + "="*50)
    print("TEST 3: Proficiency Scoring")
    print("="*50)
    
    from score_people import ProficiencyScorer
    
    enriched_people = enriched_data.get('enriched_people', [])
    topics = enriched_data.get('topics', [])
    
    scorer = ProficiencyScorer()
    scored_people = []
    
    for person in enriched_people:
        score_data = scorer.score_person(person, topics, enriched_people)
        scored_person = {**person, **score_data}
        scored_people.append(scored_person)
        
        print(f"\n  Name: {person.get('name', 'Unknown')}")
        print(f"  Score: {score_data['proficiencyScore']}")
        print(f"  Badge: {score_data['credibilityBadge']}")
        print(f"  Reasoning: {score_data['reasoning']}")
        print(f"  Breakdown:")
        for key, value in score_data['scoreBreakdown'].items():
            print(f"    {key}: {value:.2f}")
    
    result = {
        'scored_people': scored_people,
        'topics': topics,
        'summary': {
            'total_people': len(scored_people),
            'avg_score': round(sum(p['proficiencyScore'] for p in scored_people) / len(scored_people), 2) if scored_people else 0,
            'verified_experts': sum(1 for p in scored_people if p['proficiencyScore'] >= 0.75),
            'identified_contributors': sum(1 for p in scored_people if 0.60 <= p['proficiencyScore'] < 0.75)
        }
    }
    
    print(f"\n✓ Total scored: {result['summary']['total_people']}")
    print(f"✓ Average score: {result['summary']['avg_score']}")
    print(f"✓ Verified experts: {result['summary']['verified_experts']}")
    
    return result

def main():
    """Run all tests"""
    print("="*50)
    print("AI ENRICHMENT PIPELINE TEST")
    print("="*50)
    print("\nThis test uses mock data and spaCy (no API calls)")
    print("For full testing with real APIs, use individual scripts")
    
    # Test 1: Entity Extraction
    candidates_data = test_entity_extraction()
    if not candidates_data or not candidates_data['candidates']:
        print("\n✗ Cannot continue - no candidates extracted")
        return 1
    
    # Test 2: Disambiguation (mock)
    enriched_data = test_disambiguation(candidates_data)
    if not enriched_data or not enriched_data['enriched_people']:
        print("\n✗ Cannot continue - no enriched data")
        return 1
    
    # Test 3: Scoring
    scored_data = test_scoring(enriched_data)
    if not scored_data:
        print("\n✗ Scoring failed")
        return 1
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print("✓ Entity extraction: PASSED")
    print("✓ Disambiguation: PASSED (mock)")
    print("✓ Scoring: PASSED")
    print("\nAll pipeline components working!")
    print("\nNext steps:")
    print("1. Install packages: pip install -r config/requirements.txt")
    print("2. Set up HF_TOKEN for diarization")
    print("3. Test with real audio: python utils/diarize.py --audio <file>")
    print("4. Test with Ollama: python utils/extract_entities.py --transcript <file>")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
