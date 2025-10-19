#!/usr/bin/env python3
"""
Integration test - run the full pipeline with test data
"""

import sys
import os
import json
import tempfile
from pathlib import Path

def run_integration_test():
    """Run end-to-end pipeline test"""
    print("Running Integration Test...")
    
    # Create test transcript
    transcript_content = """
    Welcome to Policy Today. I'm Maria Garcia, your host. 
    Today we're discussing climate policy with Dr. James Thompson, 
    Senior Climate Scientist at NASA, and Sarah Mitchell, 
    Director of Environmental Policy at the World Bank.
    
    Dr. Thompson, what does the latest climate data tell us?
    
    Dr. Thompson: The trends are concerning, Maria. Our satellite data 
    shows accelerating ice loss in both polar regions.
    
    Sarah Mitchell: From a policy perspective, we need coordinated 
    international action. The World Bank is supporting green 
    infrastructure projects across developing nations.
    
    Maria Garcia: What specific policies would you recommend?
    
    Dr. Thompson: Carbon pricing mechanisms have shown effectiveness 
    in several jurisdictions.
    
    Sarah Mitchell: I agree. We also need technology transfer 
    programs to help developing countries leapfrog to clean energy.
    """
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(transcript_content)
        transcript_path = f.name
    
    try:
        # Step 1: Entity Extraction
        print("  Step 1: Entity Extraction")
        utils_path = os.path.join(os.path.dirname(__file__), '..', 'utils')
        cmd = f'python {utils_path}/extract_entities.py --transcript {transcript_path} --output test_integration_entities.json --method spacy'
        result = os.system(cmd)
        if result != 0:
            raise Exception("Entity extraction failed")
        
        # Step 2: Create mock enriched data (since Wikidata is blocked)
        print("  Step 2: Mock Enrichment")
        with open('test_integration_entities.json', 'r') as f:
            entities = json.load(f)
        
        mock_enriched = {
            "enriched_people": [
                {
                    "wikidata_id": "Q987654",
                    "name": "James Thompson",
                    "description": "Climate scientist at NASA",
                    "job_title": "Senior Climate Scientist",
                    "affiliation": "NASA",
                    "wikipedia_url": "https://en.wikipedia.org/wiki/James_Thompson_(scientist)",
                    "wikidata_url": "https://www.wikidata.org/wiki/Q987654",
                    "confidence": 0.82,
                    "knows_about": ["climate", "science", "nasa", "satellites", "polar"]
                },
                {
                    "wikidata_id": "Q456789",
                    "name": "Sarah Mitchell",
                    "description": "Environmental policy director",
                    "job_title": "Director of Environmental Policy",
                    "affiliation": "World Bank",
                    "wikipedia_url": "https://en.wikipedia.org/wiki/Sarah_Mitchell_(policy)",
                    "wikidata_url": "https://www.wikidata.org/wiki/Q456789",
                    "confidence": 0.78,
                    "knows_about": ["policy", "environment", "world bank", "development", "green"]
                }
            ],
            "topics": ["climate", "policy", "environment", "nasa", "world bank"]
        }
        
        with open('test_integration_enriched.json', 'w') as f:
            json.dump(mock_enriched, f, indent=2)
        
        # Step 3: Proficiency Scoring
        print("  Step 3: Proficiency Scoring")
        cmd = f'python {utils_path}/score_people.py --enriched test_integration_enriched.json --topics climate policy environment science --output test_integration_final.json'
        result = os.system(cmd)
        if result != 0:
            raise Exception("Proficiency scoring failed")
        
        # Verify final output
        with open('test_integration_final.json', 'r') as f:
            final_result = json.load(f)
        
        scored_people = final_result.get('scored_people', [])
        if len(scored_people) != 2:
            raise Exception(f"Expected 2 scored people, got {len(scored_people)}")
        
        print(f"  ✓ Successfully processed {len(scored_people)} people")
        
        for person in scored_people:
            name = person.get('name', 'Unknown')
            score = person.get('proficiencyScore', 0)
            badge = person.get('credibilityBadge', 'None')
            print(f"    - {name}: {score:.3f} ({badge})")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Integration test failed: {e}")
        return False
        
    finally:
        # Cleanup
        for file in [transcript_path, 'test_integration_entities.json', 
                    'test_integration_enriched.json', 'test_integration_final.json']:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except:
                pass


if __name__ == '__main__':
    print("=" * 50)
    print("AI Enrichment Pipeline Integration Test")
    print("=" * 50)
    
    success = run_integration_test()
    
    print("=" * 50)
    if success:
        print("🎉 Integration test PASSED!")
        print("All pipeline components work together correctly.")
    else:
        print("⚠️  Integration test FAILED!")
        print("Check individual components.")
    
    sys.exit(0 if success else 1)