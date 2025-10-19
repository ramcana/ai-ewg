#!/usr/bin/env python3
"""
Entity extraction using LLM (Ollama) or spaCy
Extracts person names, roles, and organizations from transcript
"""

import argparse
import json
import sys
import os
import re
from pathlib import Path

def extract_with_llm(transcript_text, model='mistral', ollama_url='http://localhost:11434'):
    """
    Extract entities using local LLM via Ollama with journalistic focus
    """
    try:
        import requests
    except ImportError:
        print("ERROR: requests package required", file=sys.stderr)
        sys.exit(1)
    
    # Prepare enhanced prompt for journalistic entity extraction
    prompt = f"""
Extract people, their roles, and organizations from this interview/news transcript with journalistic standards.
Focus on interview participants, quoted authorities, and newsworthy figures.

Transcript:
{transcript_text[:4000]}...

Return JSON with this exact format:
{{
  "candidates": [
    {{
      "name": "Full Name",
      "role_guess": "Job Title or Role",
      "org_guess": "Organization Name",
      "quotes": ["direct quotes or mentions of this person"],
      "confidence": 0.85,
      "journalistic_relevance": "high|medium|low",
      "authority_indicators": ["expertise markers found"],
      "context": "brief context about their relevance"
    }}
  ],
  "topics": ["topic1", "topic2", "topic3"],
  "journalistic_focus": {{
    "main_story_angle": "primary story focus",
    "key_stakeholders": ["main people involved"],
    "credibility_factors": ["factors that enhance story credibility"]
  }}
}}

Journalistic Standards:
- Prioritize people with clear expertise, authority, or direct involvement
- Mark relevance: "high" for key sources/experts, "medium" for supporting voices, "low" for mentions
- Include authority indicators: titles, credentials, institutional affiliations
- Extract 5-8 main topics with journalistic value
- Confidence: 0.9+ for clear attribution, 0.7+ for likely sources, 0.5+ for uncertain mentions
- Focus on credible, verifiable sources suitable for news reporting
"""
    
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            },
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.status_code}")
        
        result_text = response.json().get('response', '')
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            raise Exception("No valid JSON found in LLM response")
            
    except Exception as e:
        print(f"ERROR: LLM extraction failed: {e}", file=sys.stderr)
        print("Falling back to spaCy method...", file=sys.stderr)
        return extract_with_spacy(transcript_text)


def extract_with_spacy(transcript_text):
    """
    Extract entities using spaCy NER
    """
    try:
        import spacy
        from collections import Counter
    except ImportError:
        print("ERROR: spaCy not installed. Run: pip install spacy", file=sys.stderr)
        sys.exit(1)
    
    try:
        nlp = spacy.load('en_core_web_lg')
    except OSError:
        print("ERROR: spaCy model not found. Run: python -m spacy download en_core_web_lg", file=sys.stderr)
        sys.exit(1)
    
    # Process text
    doc = nlp(transcript_text)
    
    # Extract entities with journalistic focus
    people = []
    organizations = []
    topics = []
    
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            people.append(ent.text.strip())
        elif ent.label_ in ["ORG", "GPE"]:
            organizations.append(ent.text.strip())
        elif ent.label_ in ["PRODUCT", "EVENT", "LAW", "LANGUAGE", "MONEY", "PERCENT"]:
            topics.append(ent.text.lower().strip())
    
    # Count occurrences and filter
    person_counts = Counter(people)
    org_counts = Counter(organizations)
    
    # Build candidates with journalistic relevance
    candidates = []
    processed_names = set()
    
    for person, count in person_counts.most_common(15):  # Increased to capture more potential sources
        # Skip if already processed or too short
        if person.lower() in processed_names or len(person.split()) < 2:
            continue
        
        processed_names.add(person.lower())
        
        # Find context around mentions
        quotes = []
        context_sentences = []
        for sent in doc.sents:
            if person.lower() in sent.text.lower():
                quotes.append(sent.text.strip())
                context_sentences.append(sent.text.lower())
        
        # Enhanced role and organization detection
        role_guess = ""
        org_guess = ""
        authority_indicators = []
        
        context = " ".join(context_sentences[:5]).lower()
        
        # Enhanced role detection with journalistic focus
        role_patterns = [
            (r'(chief|senior|deputy|assistant|associate)\s+(\w+)', 'executive'),
            (r'(director|manager|head)\s+of\s+(\w+)', 'leadership'),
            (r'(professor|dr\.|doctor)\s+(\w+)', 'academic'),
            (r'(minister|secretary|commissioner|governor)', 'government'),
            (r'(economist|analyst|researcher|expert)', 'expert'),
            (r'(spokesperson|representative)', 'communications'),
            (r'(ceo|president|chairman)', 'executive')
        ]
        
        for pattern, category in role_patterns:
            match = re.search(pattern, context)
            if match:
                role_guess = match.group().title()
                authority_indicators.append(category)
                break
        
        # Find most likely organization with confidence scoring
        org_confidence = 0
        for org, org_count in org_counts.most_common(8):
            if org.lower() in context:
                if not org_guess or org_count > org_confidence:
                    org_guess = org
                    org_confidence = org_count
        
        # Determine journalistic relevance
        relevance = "low"
        if authority_indicators or role_guess:
            relevance = "medium"
        
        # High relevance indicators
        high_relevance_terms = [
            'minister', 'secretary', 'director', 'chief', 'president',
            'professor', 'doctor', 'expert', 'economist', 'analyst'
        ]
        
        if any(term in context for term in high_relevance_terms):
            relevance = "high"
        
        # Calculate confidence with journalistic factors
        base_confidence = min(0.9, 0.4 + (count * 0.1))
        
        # Boost confidence for authority indicators
        if authority_indicators:
            base_confidence = min(0.95, base_confidence + 0.15)
        
        # Boost for clear organizational affiliation
        if org_guess and org_confidence > 1:
            base_confidence = min(0.9, base_confidence + 0.1)
        
        # Create context summary
        context_summary = f"Mentioned {count} times"
        if role_guess:
            context_summary += f" as {role_guess}"
        if org_guess:
            context_summary += f" from {org_guess}"
        
        candidates.append({
            "name": person,
            "role_guess": role_guess,
            "org_guess": org_guess,
            "quotes": quotes[:3],  # First 3 relevant quotes
            "confidence": base_confidence,
            "journalistic_relevance": relevance,
            "authority_indicators": authority_indicators,
            "context": context_summary
        })
    
    # Extract topics with journalistic focus
    topic_words = []
    for token in doc:
        if (token.pos_ in ['NOUN', 'PROPN'] and 
            len(token.text) > 3 and 
            not token.is_stop and 
            not token.is_punct):
            topic_words.append(token.lemma_.lower())
    
    topic_counts = Counter(topic_words)
    
    # Filter topics for journalistic relevance
    journalistic_topics = []
    for word, count in topic_counts.most_common(20):
        if count >= 2:
            # Skip overly generic terms
            generic_terms = ['thing', 'people', 'time', 'way', 'year', 'day']
            if word not in generic_terms:
                journalistic_topics.append(word)
    
    # Identify main story elements
    main_story_angle = "General discussion"
    key_stakeholders = [c['name'] for c in candidates[:3] if c['journalistic_relevance'] == 'high']
    
    # Look for story angle indicators
    story_indicators = {
        'policy': ['policy', 'regulation', 'law', 'government'],
        'economic': ['economy', 'market', 'financial', 'economic', 'money'],
        'health': ['health', 'medical', 'healthcare', 'disease'],
        'technology': ['technology', 'digital', 'tech', 'innovation'],
        'environment': ['climate', 'environment', 'energy', 'green']
    }
    
    for angle, keywords in story_indicators.items():
        if any(keyword in journalistic_topics for keyword in keywords):
            main_story_angle = f"{angle.title()} focus"
            break
    
    # Identify credibility factors
    credibility_factors = []
    if any(c['authority_indicators'] for c in candidates):
        credibility_factors.append("Expert sources identified")
    if any(c['org_guess'] for c in candidates):
        credibility_factors.append("Institutional affiliations present")
    if len([c for c in candidates if c['confidence'] > 0.7]) >= 2:
        credibility_factors.append("Multiple high-confidence sources")
    
    return {
        "candidates": candidates,
        "topics": journalistic_topics[:10],  # Top 10 journalistic topics
        "journalistic_focus": {
            "main_story_angle": main_story_angle,
            "key_stakeholders": key_stakeholders,
            "credibility_factors": credibility_factors
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Extract entities from transcript')
    parser.add_argument('--transcript', required=True, help='Path to transcript file')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--method', default='llm', choices=['llm', 'spacy'], 
                       help='Extraction method')
    parser.add_argument('--model', default='mistral', help='Ollama model name')
    parser.add_argument('--ollama_url', default='http://localhost:11434', 
                       help='Ollama API URL')
    
    args = parser.parse_args()
    
    # Read transcript
    try:
        with open(args.transcript, 'r', encoding='utf-8') as f:
            transcript_text = f.read()
    except Exception as e:
        print(f"ERROR: Cannot read transcript: {e}", file=sys.stderr)
        sys.exit(1)
    
    if not transcript_text.strip():
        print("ERROR: Transcript is empty", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory if needed
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Extract entities
    try:
        if args.method == 'llm':
            result = extract_with_llm(transcript_text, args.model, args.ollama_url)
        else:
            result = extract_with_spacy(transcript_text)
        
        # Add metadata and apply confidence scoring aligned with editorial standards
        result['transcript_file'] = args.transcript
        result['extraction_method'] = args.method
        result['model_used'] = args.model if args.method == 'llm' else 'en_core_web_lg'
        
        # Apply editorial confidence thresholds
        editorial_candidates = []
        for candidate in result.get('candidates', []):
            # Apply minimum confidence threshold for editorial standards
            if candidate.get('confidence', 0) >= 0.5:  # Editorial minimum
                # Adjust confidence based on journalistic relevance
                relevance = candidate.get('journalistic_relevance', 'low')
                if relevance == 'high':
                    candidate['editorial_confidence'] = min(1.0, candidate['confidence'] + 0.1)
                elif relevance == 'medium':
                    candidate['editorial_confidence'] = candidate['confidence']
                else:
                    candidate['editorial_confidence'] = max(0.3, candidate['confidence'] - 0.1)
                
                editorial_candidates.append(candidate)
        
        result['candidates'] = editorial_candidates
        result['editorial_filtering_applied'] = True
        result['original_candidate_count'] = len(result.get('candidates', []))
        result['filtered_candidate_count'] = len(editorial_candidates)
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Extracted {len(result['candidates'])} candidates", file=sys.stderr)
        print(f"✓ Identified {len(result['topics'])} topics", file=sys.stderr)
        print(f"✓ Method used: {args.method}", file=sys.stderr)
        print(f"✓ Output saved to: {args.output}", file=sys.stderr)
        
        # Show preview
        for i, candidate in enumerate(result['candidates'][:3]):
            print(f"  {i+1}. {candidate['name']} - {candidate.get('role_guess', 'N/A')} ({candidate.get('confidence', 0):.2f})", file=sys.stderr)
        
    except Exception as e:
        print(f"ERROR: Entity extraction failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()