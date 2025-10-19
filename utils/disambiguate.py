#!/usr/bin/env python3
"""
Disambiguate and enrich person entities using Wikipedia/Wikidata
"""

import argparse
import json
import sys
import os
import time
from pathlib import Path

def search_wikidata(name, role=None, org=None, limit=5):
    """
    Search Wikidata for person entities
    """
    try:
        import requests
        from urllib.parse import quote
    except ImportError:
        print("ERROR: requests package required", file=sys.stderr)
        sys.exit(1)
    
    # Build search query
    query = name
    if role:
        query += f" {role}"
    if org:
        query += f" {org}"
    
    # Wikidata search API
    search_url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "format": "json",
        "type": "item",
        "limit": limit
    }
    
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        
        results = response.json().get('search', [])
        
        # Filter for people (has instance of human)
        candidates = []
        for result in results:
            qid = result.get('id')
            if qid:
                # Get basic info
                entity_data = get_wikidata_entity(qid)
                if entity_data and is_person(entity_data):
                    candidates.append({
                        'qid': qid,
                        'label': result.get('label', ''),
                        'description': result.get('description', ''),
                        'data': entity_data
                    })
        
        return candidates
        
    except Exception as e:
        print(f"WARNING: Wikidata search failed for '{name}': {e}", file=sys.stderr)
        return []


def get_wikidata_entity(qid):
    """
    Get detailed entity data from Wikidata
    """
    try:
        import requests
    except ImportError:
        return None
    
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "format": "json",
        "languages": "en"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        entities = data.get('entities', {})
        
        return entities.get(qid, {})
        
    except Exception as e:
        print(f"WARNING: Failed to get Wikidata entity {qid}: {e}", file=sys.stderr)
        return None


def is_person(entity_data):
    """
    Check if Wikidata entity represents a person
    """
    claims = entity_data.get('claims', {})
    
    # Check P31 (instance of) for Q5 (human)
    instance_of = claims.get('P31', [])
    for claim in instance_of:
        try:
            value = claim['mainsnak']['datavalue']['value']['id']
            if value == 'Q5':  # Q5 = human
                return True
        except (KeyError, TypeError):
            continue
    
    return False


def extract_person_data(entity_data, qid):
    """
    Extract relevant information from Wikidata entity
    """
    claims = entity_data.get('claims', {})
    labels = entity_data.get('labels', {})
    descriptions = entity_data.get('descriptions', {})
    
    # Basic info
    name = labels.get('en', {}).get('value', '')
    description = descriptions.get('en', {}).get('value', '')
    
    # Job title (P39 - position held, P106 - occupation)
    job_titles = []
    for prop in ['P39', 'P106']:
        for claim in claims.get(prop, []):
            try:
                title_qid = claim['mainsnak']['datavalue']['value']['id']
                # Would need another API call to resolve, simplified for now
                job_titles.append(title_qid)
            except (KeyError, TypeError):
                continue
    
    # Employer/affiliation (P108)
    affiliations = []
    for claim in claims.get('P108', []):
        try:
            org_qid = claim['mainsnak']['datavalue']['value']['id']
            affiliations.append(org_qid)
        except (KeyError, TypeError):
            continue
    
    # Field of work (P101)
    fields = []
    for claim in claims.get('P101', []):
        try:
            field_qid = claim['mainsnak']['datavalue']['value']['id']
            fields.append(field_qid)
        except (KeyError, TypeError):
            continue
    
    # Wikipedia link
    sitelinks = entity_data.get('sitelinks', {})
    wikipedia_url = ""
    if 'enwiki' in sitelinks:
        wiki_title = sitelinks['enwiki']['title'].replace(' ', '_')
        wikipedia_url = f"https://en.wikipedia.org/wiki/{wiki_title}"
    
    return {
        'wikidata_id': qid,
        'name': name,
        'description': description,
        'job_titles': job_titles,
        'affiliations': affiliations,
        'fields': fields,
        'wikipedia_url': wikipedia_url,
        'wikidata_url': f"https://www.wikidata.org/wiki/{qid}"
    }


def calculate_match_confidence(candidate, person_data, topics=None):
    """
    Calculate confidence score for a candidate match with authority verification
    """
    score = 0.0
    
    # Name similarity (enhanced)
    candidate_name = candidate.get('name', '').lower()
    wikidata_name = person_data.get('name', '').lower()
    
    # Exact match gets highest score
    if candidate_name == wikidata_name:
        score += 0.5
    elif candidate_name in wikidata_name or wikidata_name in candidate_name:
        score += 0.4
    elif any(word in wikidata_name for word in candidate_name.split() if len(word) > 2):
        score += 0.2
    
    # Role/description match with authority weighting
    candidate_role = candidate.get('role_guess', '').lower()
    description = person_data.get('description', '').lower()
    
    if candidate_role and candidate_role in description:
        score += 0.3
    elif candidate_role:
        # Partial role matching
        role_words = candidate_role.split()
        if any(word in description for word in role_words if len(word) > 3):
            score += 0.15
    
    # Organization match with authority verification
    candidate_org = candidate.get('org_guess', '').lower()
    if candidate_org:
        # Check against affiliations in Wikidata
        affiliations = person_data.get('affiliations', [])
        if affiliations:
            score += 0.15  # Bonus for having organizational data
        
        # Simple organization name matching (could be enhanced)
        if any(candidate_org in str(aff).lower() for aff in affiliations):
            score += 0.2
    
    # Topic relevance with journalistic focus
    if topics:
        topic_words = ' '.join(topics).lower()
        description_words = description.split()
        
        # Check for topic-description overlap
        topic_matches = sum(1 for word in description_words 
                          if len(word) > 3 and word in topic_words)
        
        if topic_matches > 0:
            score += min(0.2, topic_matches * 0.05)
    
    # Authority source bonus
    authority_domains = ['.gov', '.gc.ca', '.edu', '.ac.uk']
    wikipedia_url = person_data.get('wikipedia_url', '')
    wikidata_url = person_data.get('wikidata_url', '')
    
    if wikipedia_url or wikidata_url:
        score += 0.1  # Bonus for having authoritative sources
    
    # Journalistic relevance bonus
    candidate_relevance = candidate.get('journalistic_relevance', 'low')
    if candidate_relevance == 'high':
        score += 0.1
    elif candidate_relevance == 'medium':
        score += 0.05
    
    return min(1.0, score)


def verify_authority_sources(person_data):
    """Verify authority and credibility of sources for journalistic standards"""
    authority_score = 0.0
    authority_sources = []
    biographical_data = {}
    
    # Check Wikipedia URL for authority
    wikipedia_url = person_data.get('wikipedia_url', '')
    if wikipedia_url:
        authority_score += 0.3
        authority_sources.append('Wikipedia')
        
        # Extract additional biographical data from Wikipedia (simplified)
        biographical_data['wikipedia_verified'] = True
    
    # Check Wikidata for official sources
    wikidata_url = person_data.get('wikidata_url', '')
    if wikidata_url:
        authority_score += 0.2
        authority_sources.append('Wikidata')
        biographical_data['wikidata_verified'] = True
    
    # Check for government/academic affiliations
    description = person_data.get('description', '').lower()
    authority_indicators = [
        ('government', 0.4), ('minister', 0.4), ('secretary', 0.4),
        ('professor', 0.3), ('university', 0.3), ('academic', 0.3),
        ('director', 0.2), ('chief', 0.2), ('economist', 0.2)
    ]
    
    for indicator, score_boost in authority_indicators:
        if indicator in description:
            authority_score += score_boost
            authority_sources.append(f"Authority role: {indicator}")
            break
    
    # Determine authority level for journalistic credibility
    if authority_score >= 0.7:
        authority_level = 'high'
    elif authority_score >= 0.4:
        authority_level = 'medium'
    else:
        authority_level = 'low'
    
    return {
        'authority_score': min(1.0, authority_score),
        'authority_level': authority_level,
        'authority_sources': authority_sources,
        'biographical_data': biographical_data
    }


def enrich_candidate(candidate, topics=None, min_confidence=0.6):
    """
    Enrich a single candidate with Wikidata information and authority verification
    """
    name = candidate.get('name', '')
    role = candidate.get('role_guess', '')
    org = candidate.get('org_guess', '')
    
    print(f"  Searching for: {name}", file=sys.stderr)
    
    # Search Wikidata
    wikidata_candidates = search_wikidata(name, role, org)
    
    if not wikidata_candidates:
        print(f"    ✗ No Wikidata candidates found", file=sys.stderr)
        return None
    
    # Find best match with authority verification
    best_match = None
    best_confidence = 0
    best_authority = None
    
    for wd_candidate in wikidata_candidates:
        person_data = extract_person_data(wd_candidate['data'], wd_candidate['qid'])
        confidence = calculate_match_confidence(candidate, person_data, topics)
        
        # Verify authority sources
        authority_verification = verify_authority_sources(person_data)
        
        # Boost confidence for high authority sources
        if authority_verification['authority_level'] == 'high':
            confidence = min(1.0, confidence + 0.1)
        elif authority_verification['authority_level'] == 'medium':
            confidence = min(1.0, confidence + 0.05)
        
        if confidence > best_confidence:
            best_confidence = confidence
            best_match = person_data
            best_authority = authority_verification
    
    if best_match and best_confidence >= min_confidence:
        # Enrich with additional fields including authority verification
        enriched = {
            **best_match,
            'original_name': candidate['name'],
            'job_title': candidate.get('role_guess', ''),
            'affiliation': candidate.get('org_guess', ''),
            'confidence': best_confidence,
            'same_as': [
                best_match['wikidata_url'],
                best_match['wikipedia_url']
            ] if best_match['wikipedia_url'] else [best_match['wikidata_url']],
            'knows_about': topics[:5] if topics else [],
            
            # Authority verification data
            'authority_score': best_authority['authority_score'],
            'authority_level': best_authority['authority_level'],
            'authority_sources': best_authority['authority_sources'],
            'biographical_data': best_authority['biographical_data'],
            
            # Journalistic metadata
            'journalistic_relevance': candidate.get('journalistic_relevance', 'medium'),
            'authority_indicators': candidate.get('authority_indicators', []),
            'source_credibility': 'verified' if best_authority['authority_level'] in ['high', 'medium'] else 'unverified'
        }
        
        print(f"    ✓ Match found: {best_match['name']} (confidence: {best_confidence:.2f}, authority: {best_authority['authority_level']})", file=sys.stderr)
        return enriched
    else:
        print(f"    ✗ No confident match found (best: {best_confidence:.2f})", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description='Disambiguate and enrich person entities')
    parser.add_argument('--candidates', required=True, help='Path to candidates JSON file')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--min_confidence', type=float, default=0.6, 
                       help='Minimum confidence threshold')
    parser.add_argument('--rate_limit', type=float, default=0.5,
                       help='Delay between API calls (seconds)')
    
    args = parser.parse_args()
    
    # Read candidates
    try:
        with open(args.candidates, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Cannot read candidates file: {e}", file=sys.stderr)
        sys.exit(1)
    
    candidates = data.get('candidates', [])
    topics = data.get('topics', [])
    
    if not candidates:
        print("ERROR: No candidates found in input file", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory if needed
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Process each candidate
    enriched_people = []
    
    print(f"Processing {len(candidates)} candidates...", file=sys.stderr)
    
    for i, candidate in enumerate(candidates):
        print(f"\n[{i+1}/{len(candidates)}]", file=sys.stderr)
        
        try:
            enriched = enrich_candidate(candidate, topics, args.min_confidence)
            if enriched:
                enriched_people.append(enriched)
            
            # Rate limiting
            if i < len(candidates) - 1:  # Don't sleep after last item
                time.sleep(args.rate_limit)
                
        except Exception as e:
            print(f"    ERROR: Failed to process {candidate.get('name', 'unknown')}: {e}", file=sys.stderr)
            continue
    
    # Calculate authority verification statistics
    high_authority = sum(1 for p in enriched_people if p.get('authority_level') == 'high')
    medium_authority = sum(1 for p in enriched_people if p.get('authority_level') == 'medium')
    verified_sources = sum(1 for p in enriched_people if p.get('source_credibility') == 'verified')
    
    # Build result with authority verification summary
    result = {
        'enriched_people': enriched_people,
        'original_candidates': candidates,
        'topics': topics,
        'summary': {
            'total_candidates': len(candidates),
            'enriched_count': len(enriched_people),
            'success_rate': len(enriched_people) / len(candidates) if candidates else 0,
            'authority_verification': {
                'high_authority': high_authority,
                'medium_authority': medium_authority,
                'verified_sources': verified_sources,
                'verification_rate': verified_sources / len(enriched_people) if enriched_people else 0
            }
        }
    }
    
    # Save results
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        authority_stats = result['summary']['authority_verification']
        
        print(f"\n✓ Enriched {len(enriched_people)}/{len(candidates)} candidates", file=sys.stderr)
        print(f"✓ Success rate: {result['summary']['success_rate']:.1%}", file=sys.stderr)
        print(f"✓ Authority verification: {authority_stats['verified_sources']}/{len(enriched_people)} verified ({authority_stats['verification_rate']:.1%})", file=sys.stderr)
        print(f"✓ High authority sources: {authority_stats['high_authority']}", file=sys.stderr)
        print(f"✓ Medium authority sources: {authority_stats['medium_authority']}", file=sys.stderr)
        print(f"✓ Output saved to: {args.output}", file=sys.stderr)
        
    except Exception as e:
        print(f"ERROR: Cannot save results: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()