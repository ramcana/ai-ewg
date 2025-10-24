#!/usr/bin/env python3
"""
Calculate proficiency/credibility scores for enriched people
"""

import argparse
import json
import sys
import os
import re
from pathlib import Path

class ProficiencyScorer:
    """
    Calculate credibility scores based on expertise and authority
    """
    
    def __init__(self):
        # Authority domains (higher credibility)
        self.authority_domains = {
            '.gov', '.gc.ca', '.edu', '.ac.uk', '.org'  # Government, education, major orgs
        }
        
        # Role keywords that indicate expertise
        self.expert_roles = {
            'chief', 'senior', 'director', 'professor', 'doctor', 'dr.',
            'minister', 'secretary', 'commissioner', 'governor', 'economist',
            'analyst', 'researcher', 'scientist', 'expert', 'specialist'
        }
    
    def score_person(self, person, episode_topics=None, all_people=None):
        """
        Calculate proficiency score for a person with journalistic standards
        
        Args:
            person: Enriched person data
            episode_topics: List of episode topics
            all_people: List of all people (for ambiguity detection)
        
        Returns:
            dict: Score data with breakdown and editorial decision support
        """
        score_breakdown = {
            'roleMatch': 0.0,
            'authorityDomain': 0.0,
            'knowledgeBase': 0.0,
            'publications': 0.0,
            'recency': 0.0,
            'journalisticRelevance': 0.0,
            'authorityVerification': 0.0,
            'ambiguityPenalty': 0.0
        }
        
        # 1. Role Match (25% weight - reduced to make room for journalistic factors)
        role_score = self._score_role_match(person, episode_topics)
        score_breakdown['roleMatch'] = role_score * 0.25
        
        # 2. Authority Domain (20% weight)
        authority_score = self._score_authority_domain(person)
        score_breakdown['authorityDomain'] = authority_score * 0.20
        
        # 3. Knowledge Base Presence (15% weight)
        kb_score = self._score_knowledge_base(person)
        score_breakdown['knowledgeBase'] = kb_score * 0.15
        
        # 4. Publications/Research (10% weight)
        pub_score = self._score_publications(person)
        score_breakdown['publications'] = pub_score * 0.10
        
        # 5. Recency (10% weight)
        recency_score = self._score_recency(person)
        score_breakdown['recency'] = recency_score * 0.10
        
        # 6. Journalistic Relevance (10% weight - NEW)
        journalistic_score = self._score_journalistic_relevance(person, episode_topics)
        score_breakdown['journalisticRelevance'] = journalistic_score * 0.10
        
        # 7. Authority Verification (10% weight - NEW)
        verification_score = self._score_authority_verification(person)
        score_breakdown['authorityVerification'] = verification_score * 0.10
        
        # 8. Ambiguity Penalty (up to -20%)
        ambiguity_penalty = self._score_ambiguity(person, all_people)
        score_breakdown['ambiguityPenalty'] = -ambiguity_penalty * 0.20
        
        # Calculate total score
        total_score = sum(score_breakdown.values())
        total_score = max(0.0, min(1.0, total_score))  # Clamp to [0, 1]
        
        # Get authority level for badge determination
        authority_level = person.get('authority_level', 'low')
        
        # Determine badge with journalistic standards
        badge = self._get_credibility_badge(total_score, authority_level)
        
        # Generate reasoning for editorial decision support
        reasoning = self._generate_reasoning(person, score_breakdown, episode_topics)
        
        # Generate editorial decision support
        editorial_decision = self._generate_editorial_decision(total_score, authority_level, person)
        
        # Create verification badge assignment
        verification_badge = self._assign_verification_badge(total_score, authority_level, person)
        
        return {
            'proficiencyScore': round(total_score, 3),
            'credibilityBadge': badge,
            'verificationBadge': verification_badge,
            'scoreBreakdown': {k: round(v, 3) for k, v in score_breakdown.items()},
            'reasoning': reasoning,
            'editorialDecision': editorial_decision,
            'authorityLevel': authority_level,
            'journalisticRelevance': person.get('journalistic_relevance', 'medium')
        }
    
    def _score_role_match(self, person, episode_topics):
        """Score how well person's role matches episode topics"""
        if not episode_topics:
            return 0.5  # Neutral if no topics
        
        role = (person.get('job_title', '') + ' ' + 
                person.get('description', '') + ' ' +
                ' '.join(person.get('knows_about', []))).lower()
        
        topic_text = ' '.join(episode_topics).lower()
        
        # Check for direct matches
        matches = 0
        total_topics = len(episode_topics)
        
        for topic in episode_topics:
            topic_words = topic.lower().split()
            for word in topic_words:
                if len(word) > 3 and word in role:
                    matches += 1
                    break
        
        # Bonus for expert-level roles
        expert_bonus = 0
        for expert_term in self.expert_roles:
            if expert_term in role:
                expert_bonus = 0.2
                break
        
        base_score = matches / total_topics if total_topics > 0 else 0
        return min(1.0, base_score + expert_bonus)
    
    def _score_authority_domain(self, person):
        """Score based on institutional authority"""
        affiliation = person.get('affiliation', '').lower()
        same_as = person.get('same_as', [])
        
        # Check affiliation for authority domains
        for domain in self.authority_domains:
            if domain in affiliation:
                return 1.0
        
        # Check URLs for authority domains
        for url in same_as:
            for domain in self.authority_domains:
                if domain in url.lower():
                    return 0.8
        
        # Check for major organizations (simplified)
        authority_orgs = [
            'bank of canada', 'government', 'university', 'college',
            'federal reserve', 'european central bank', 'imf', 'world bank'
        ]
        
        for org in authority_orgs:
            if org in affiliation:
                return 0.9
        
        return 0.3  # Default for non-authority sources
    
    def _score_knowledge_base(self, person):
        """Score based on presence in knowledge bases"""
        has_wikidata = bool(person.get('wikidata_id'))
        has_wikipedia = bool(person.get('wikipedia_url'))
        
        if has_wikidata and has_wikipedia:
            return 1.0
        elif has_wikidata or has_wikipedia:
            return 0.7
        else:
            return 0.0
    
    def _score_publications(self, person):
        """Score based on publication record (simplified)"""
        # In a full implementation, this would check Wikidata for publications
        # For now, use heuristics based on role and description
        
        role = person.get('job_title', '').lower()
        description = person.get('description', '').lower()
        
        research_indicators = [
            'professor', 'researcher', 'scientist', 'economist', 'analyst',
            'author', 'writer', 'scholar', 'academic'
        ]
        
        for indicator in research_indicators:
            if indicator in role or indicator in description:
                return 0.8
        
        return 0.3  # Default assumption
    
    def _score_recency(self, person):
        """Score based on how current the role is"""
        # In a full implementation, this would check dates from Wikidata
        # For now, assume roles are current unless indicated otherwise
        
        description = person.get('description', '').lower()
        
        # Check for past tense indicators
        past_indicators = ['former', 'ex-', 'retired', 'was', 'previously']
        
        for indicator in past_indicators:
            if indicator in description:
                return 0.5
        
        return 1.0  # Assume current
    
    def _score_journalistic_relevance(self, person, episode_topics):
        """Score based on journalistic relevance and newsworthiness"""
        relevance = person.get('journalistic_relevance', 'medium')
        
        # Base score from relevance level
        relevance_scores = {
            'high': 1.0,
            'medium': 0.6,
            'low': 0.3
        }
        
        base_score = relevance_scores.get(relevance, 0.5)
        
        # Boost for authority indicators
        authority_indicators = person.get('authority_indicators', [])
        if authority_indicators:
            base_score = min(1.0, base_score + len(authority_indicators) * 0.1)
        
        # Boost for credibility quotes
        credibility_quotes = person.get('credibility_quotes', [])
        if credibility_quotes:
            base_score = min(1.0, base_score + 0.2)
        
        return base_score
    
    def _score_authority_verification(self, person):
        """Score based on authority verification for journalistic credibility"""
        authority_level = person.get('authority_level', 'low')
        authority_score = person.get('authority_score', 0.0)
        
        # Base score from authority level
        level_scores = {
            'high': 1.0,
            'medium': 0.7,
            'low': 0.3
        }
        
        base_score = level_scores.get(authority_level, 0.3)
        
        # Adjust based on authority score
        adjusted_score = (base_score + authority_score) / 2
        
        # Boost for verified sources
        source_credibility = person.get('source_credibility', 'unverified')
        if source_credibility == 'verified':
            adjusted_score = min(1.0, adjusted_score + 0.2)
        
        # Boost for biographical data verification
        biographical_data = person.get('biographical_data', {})
        if biographical_data.get('wikipedia_verified') or biographical_data.get('wikidata_verified'):
            adjusted_score = min(1.0, adjusted_score + 0.1)
        
        return adjusted_score
    
    def _score_ambiguity(self, person, all_people):
        """Calculate penalty for ambiguous matches"""
        if not all_people or len(all_people) <= 1:
            return 0.0
        
        person_name = person.get('name', '').lower()
        
        # Check for similar names in the same episode
        similar_count = 0
        for other in all_people:
            if other.get('name', '').lower() != person_name:
                # Simple similarity check
                other_name = other.get('name', '').lower()
                if (person_name in other_name or other_name in person_name or
                    len(set(person_name.split()) & set(other_name.split())) >= 2):
                    similar_count += 1
        
        # Penalty based on number of similar matches
        return min(1.0, similar_count * 0.3)
    
    def _get_credibility_badge(self, score, authority_level=None):
        """Get credibility badge based on score and authority verification"""
        # Enhanced badge system for journalistic standards
        if score >= 0.85 and authority_level == 'high':
            return "Verified Expert"
        elif score >= 0.75:
            return "Verified Expert" if authority_level in ['high', 'medium'] else "Expert"
        elif score >= 0.65:
            return "Identified Contributor"
        elif score >= 0.50:
            return "Guest"
        elif score >= 0.35:
            return "Mentioned"
        else:
            return "Unverified"
    
    def _generate_reasoning(self, person, breakdown, topics):
        """Generate human-readable reasoning for the score with journalistic context"""
        reasons = []
        
        # Role match
        if breakdown['roleMatch'] >= 0.20:
            reasons.append("strong role-topic match")
        elif breakdown['roleMatch'] >= 0.10:
            reasons.append("moderate role-topic match")
        
        # Authority
        if breakdown['authorityDomain'] >= 0.15:
            reasons.append("authoritative institutional affiliation")
        elif breakdown['authorityDomain'] >= 0.08:
            reasons.append("recognized organization")
        
        # Knowledge base
        if breakdown['knowledgeBase'] >= 0.10:
            reasons.append("well-documented in authoritative sources")
        
        # Publications
        if breakdown['publications'] >= 0.05:
            reasons.append("research or publication background")
        
        # Journalistic relevance
        if breakdown['journalisticRelevance'] >= 0.08:
            reasons.append("high journalistic relevance")
        elif breakdown['journalisticRelevance'] >= 0.05:
            reasons.append("moderate journalistic relevance")
        
        # Authority verification
        if breakdown['authorityVerification'] >= 0.08:
            reasons.append("verified through authoritative sources")
        elif breakdown['authorityVerification'] >= 0.05:
            reasons.append("some authority verification")
        
        # Recency
        if breakdown['recency'] >= 0.08:
            reasons.append("current role")
        
        # Ambiguity
        if breakdown['ambiguityPenalty'] < -0.05:
            reasons.append("some ambiguity in identification")
        
        if not reasons:
            reasons.append("limited verification available")
        
        return "; ".join(reasons).capitalize()
    
    def _generate_editorial_decision(self, score, authority_level, person):
        """Generate editorial decision support for newsroom use"""
        if score >= 0.85 and authority_level == 'high':
            return "Recommend for prominent attribution with full credentials"
        elif score >= 0.75:
            if authority_level in ['high', 'medium']:
                return "Suitable for standard attribution with verification"
            else:
                return "Use with context and additional verification"
        elif score >= 0.65:
            return "Suitable for supporting attribution with context"
        elif score >= 0.50:
            return "Use as guest with clear context and verification"
        elif score >= 0.35:
            return "Mention only with significant additional verification"
        else:
            return "Requires substantial verification before editorial use"
    
    def _assign_verification_badge(self, score, authority_level, person):
        """Assign verification badge based on credibility scores and journalistic standards"""
        source_credibility = person.get('source_credibility', 'unverified')
        authority_sources = person.get('authority_sources', [])
        
        if score >= 0.85 and authority_level == 'high' and source_credibility == 'verified':
            return "Gold Standard"
        elif score >= 0.75 and authority_level in ['high', 'medium']:
            return "Verified Authority"
        elif score >= 0.65 and source_credibility == 'verified':
            return "Verified Source"
        elif score >= 0.50 and authority_sources:
            return "Documented"
        elif score >= 0.35:
            return "Basic Verification"
        else:
            return "Unverified"


def main():
    parser = argparse.ArgumentParser(description='Score proficiency of enriched people')
    parser.add_argument('--enriched', required=True, help='Path to enriched people JSON')
    parser.add_argument('--topics', nargs='*', help='Episode topics (space-separated)')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Read enriched data
    try:
        with open(args.enriched, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Cannot read enriched file: {e}", file=sys.stderr)
        sys.exit(1)
    
    enriched_people = data.get('enriched_people', [])
    topics = args.topics or data.get('topics', [])
    
    if not enriched_people:
        print("WARNING: No enriched people found in input file - returning empty result", file=sys.stderr)
        
        # Create output directory if needed
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Return empty but valid result
        from datetime import datetime
        empty_result = {
            'schema_version': 'ic-1.0.0',
            'scored_people': [],
            'summary': {
                'total_people': 0,
                'avg_score': 0.0,
                'badge_distribution': {},
                'authority_distribution': {},
                'verification_distribution': {},
                'journalistic_relevance': {}
            },
            'timestamp': datetime.now().isoformat()
        }
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(empty_result, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Empty result saved to: {args.output}", file=sys.stderr)
        return
    
    # Create output directory if needed
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Score each person
    scorer = ProficiencyScorer()
    scored_people = []
    
    print(f"Scoring {len(enriched_people)} people...", file=sys.stderr)
    
    for i, person in enumerate(enriched_people):
        print(f"  [{i+1}/{len(enriched_people)}] {person.get('name', 'Unknown')}", file=sys.stderr)
        
        try:
            score_data = scorer.score_person(person, topics, enriched_people)
            scored_person = {**person, **score_data}
            scored_people.append(scored_person)
            
            print(f"    Score: {score_data['proficiencyScore']:.3f} ({score_data['credibilityBadge']})", file=sys.stderr)
            
        except Exception as e:
            print(f"    ERROR: Failed to score {person.get('name', 'unknown')}: {e}", file=sys.stderr)
            continue
    
    # Calculate summary statistics with journalistic standards
    if scored_people:
        avg_score = sum(p['proficiencyScore'] for p in scored_people) / len(scored_people)
        
        # Badge-based categorization
        verified_experts = sum(1 for p in scored_people if p['credibilityBadge'] == 'Verified Expert')
        identified_contributors = sum(1 for p in scored_people if p['credibilityBadge'] == 'Identified Contributor')
        guests = sum(1 for p in scored_people if p['credibilityBadge'] == 'Guest')
        mentioned = sum(1 for p in scored_people if p['credibilityBadge'] == 'Mentioned')
        unverified = sum(1 for p in scored_people if p['credibilityBadge'] == 'Unverified')
        
        # Authority level statistics
        high_authority = sum(1 for p in scored_people if p.get('authorityLevel') == 'high')
        medium_authority = sum(1 for p in scored_people if p.get('authorityLevel') == 'medium')
        
        # Verification badge statistics
        gold_standard = sum(1 for p in scored_people if p.get('verificationBadge') == 'Gold Standard')
        verified_authority = sum(1 for p in scored_people if p.get('verificationBadge') == 'Verified Authority')
        
    else:
        avg_score = 0
        verified_experts = identified_contributors = guests = mentioned = unverified = 0
        high_authority = medium_authority = gold_standard = verified_authority = 0
    
    # Build result with enhanced journalistic statistics
    result = {
        'scored_people': scored_people,
        'topics': topics,
        'summary': {
            'total_people': len(scored_people),
            'avg_score': round(avg_score, 3),
            'credibility_badges': {
                'verified_experts': verified_experts,
                'identified_contributors': identified_contributors,
                'guests': guests,
                'mentioned': mentioned,
                'unverified': unverified
            },
            'authority_levels': {
                'high_authority': high_authority,
                'medium_authority': medium_authority,
                'low_authority': len(scored_people) - high_authority - medium_authority
            },
            'verification_badges': {
                'gold_standard': gold_standard,
                'verified_authority': verified_authority,
                'total_verified': gold_standard + verified_authority
            },
            'editorial_readiness': {
                'ready_for_attribution': verified_experts + identified_contributors,
                'requires_context': guests + mentioned,
                'needs_verification': unverified
            }
        }
    }
    
    # Save results
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        summary = result['summary']
        
        print(f"\n✓ Scored {len(scored_people)} people", file=sys.stderr)
        print(f"✓ Average score: {avg_score:.3f}", file=sys.stderr)
        print(f"✓ Credibility distribution:", file=sys.stderr)
        print(f"  - Verified experts: {summary['credibility_badges']['verified_experts']}", file=sys.stderr)
        print(f"  - Identified contributors: {summary['credibility_badges']['identified_contributors']}", file=sys.stderr)
        print(f"  - Guests: {summary['credibility_badges']['guests']}", file=sys.stderr)
        print(f"✓ Authority verification: {summary['authority_levels']['high_authority']} high, {summary['authority_levels']['medium_authority']} medium", file=sys.stderr)
        print(f"✓ Editorial readiness: {summary['editorial_readiness']['ready_for_attribution']} ready for attribution", file=sys.stderr)
        print(f"✓ Output saved to: {args.output}", file=sys.stderr)
        
    except Exception as e:
        print(f"ERROR: Cannot save results: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()