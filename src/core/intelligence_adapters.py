"""
Adapters to bridge existing utility scripts with typed intelligence models

These adapters convert between the legacy JSON outputs and the new pydantic models.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from .intelligence_models import (
    DiarizationResult, DiarizationSegment,
    EntitiesResult, EntityMention, JournalisticFocus,
    ResolutionResult, EntityResolution, EntityEvidence, DisambiguationCandidate,
    ProficiencyResult, ScoredPerson, ProficiencyScoreBreakdown
)


def adapt_diarization_result(data: Dict[str, Any]) -> DiarizationResult:
    """Convert diarization JSON to typed model"""
    segments = [
        DiarizationSegment(
            start=seg['start'],
            end=seg['end'],
            speaker=seg['speaker'],
            duration=seg['duration'],
            confidence=seg.get('confidence')
        )
        for seg in data.get('segments', [])
    ]
    
    return DiarizationResult(
        audio_file=data.get('audio_file', ''),
        num_speakers=data.get('num_speakers', 0),
        total_duration=data.get('total_duration', 0.0),
        device_used=data.get('device_used', 'unknown'),
        segments=segments,
        validation=data.get('validation'),
        consistency=data.get('consistency')
    )


def adapt_entities_result(data: Dict[str, Any]) -> EntitiesResult:
    """Convert entity extraction JSON to typed model"""
    candidates = [
        EntityMention(
            name=c['name'],
            role_guess=c.get('role_guess'),
            org_guess=c.get('org_guess'),
            quotes=c.get('quotes', []),
            confidence=c.get('confidence', 0.5),
            journalistic_relevance=c.get('journalistic_relevance', 'medium'),
            authority_indicators=c.get('authority_indicators', []),
            context=c.get('context'),
            editorial_confidence=c.get('editorial_confidence')
        )
        for c in data.get('candidates', [])
    ]
    
    # Parse journalistic focus if available
    journalistic_focus = None
    jf_data = data.get('journalistic_focus')
    if jf_data:
        journalistic_focus = JournalisticFocus(
            main_story_angle=jf_data.get('main_story_angle', 'General discussion'),
            key_stakeholders=jf_data.get('key_stakeholders', []),
            credibility_factors=jf_data.get('credibility_factors', [])
        )
    
    return EntitiesResult(
        transcript_file=data.get('transcript_file', ''),
        extraction_method=data.get('extraction_method', 'unknown'),
        model_used=data.get('model_used', 'unknown'),
        candidates=candidates,
        topics=data.get('topics', []),
        journalistic_focus=journalistic_focus,
        editorial_filtering_applied=data.get('editorial_filtering_applied', False),
        original_candidate_count=data.get('original_candidate_count', len(candidates)),
        filtered_candidate_count=data.get('filtered_candidate_count', len(candidates))
    )


def adapt_resolution_result(data: Dict[str, Any]) -> ResolutionResult:
    """Convert disambiguation JSON to typed model"""
    enriched_people = []
    
    for p in data.get('enriched_people', []):
        # Parse candidates considered (if available)
        candidates_considered = []
        for c in p.get('candidates_considered', []):
            candidates_considered.append(DisambiguationCandidate(
                qid=c.get('qid', ''),
                label=c.get('label', ''),
                description=c.get('description', ''),
                score=c.get('score', 0.0)
            ))
        
        # Parse evidence (if available)
        evidence = []
        for e in p.get('evidence', []):
            evidence.append(EntityEvidence(
                source=e.get('source', 'unknown'),
                span=e.get('span'),
                text=e.get('text'),
                timestamp_range=e.get('timestamp_range'),
                score=e.get('score', 0.0)
            ))
        
        enriched_people.append(EntityResolution(
            original_name=p.get('original_name', ''),
            wikidata_id=p.get('wikidata_id', ''),
            name=p.get('name', ''),
            description=p.get('description', ''),
            job_title=p.get('job_title'),
            affiliation=p.get('affiliation'),
            confidence=p.get('confidence', 0.0),
            same_as=p.get('same_as', []),
            knows_about=p.get('knows_about', []),
            authority_score=p.get('authority_score', 0.0),
            authority_level=p.get('authority_level', 'low'),
            authority_sources=p.get('authority_sources', []),
            biographical_data=p.get('biographical_data', {}),
            journalistic_relevance=p.get('journalistic_relevance', 'medium'),
            authority_indicators=p.get('authority_indicators', []),
            source_credibility=p.get('source_credibility', 'unverified'),
            evidence=evidence,
            candidates_considered=candidates_considered,
            decision_rule=p.get('decision_rule')
        ))
    
    # Adapt original candidates
    original_candidates = [
        EntityMention(
            name=c['name'],
            role_guess=c.get('role_guess'),
            org_guess=c.get('org_guess'),
            quotes=c.get('quotes', []),
            confidence=c.get('confidence', 0.5),
            journalistic_relevance=c.get('journalistic_relevance', 'medium'),
            authority_indicators=c.get('authority_indicators', []),
            context=c.get('context')
        )
        for c in data.get('original_candidates', [])
    ]
    
    return ResolutionResult(
        enriched_people=enriched_people,
        original_candidates=original_candidates,
        topics=data.get('topics', []),
        summary=data.get('summary', {})
    )


def adapt_proficiency_result(data: Dict[str, Any]) -> ProficiencyResult:
    """Convert proficiency scoring JSON to typed model"""
    scored_people = []
    
    for p in data.get('scored_people', []):
        # Parse score breakdown
        breakdown_data = p.get('scoreBreakdown', {})
        breakdown = ProficiencyScoreBreakdown(
            roleMatch=breakdown_data.get('roleMatch', 0.0),
            authorityDomain=breakdown_data.get('authorityDomain', 0.0),
            knowledgeBase=breakdown_data.get('knowledgeBase', 0.0),
            publications=breakdown_data.get('publications', 0.0),
            recency=breakdown_data.get('recency', 0.0),
            journalisticRelevance=breakdown_data.get('journalisticRelevance', 0.0),
            authorityVerification=breakdown_data.get('authorityVerification', 0.0),
            ambiguityPenalty=breakdown_data.get('ambiguityPenalty', 0.0)
        )
        
        scored_people.append(ScoredPerson(
            original_name=p.get('original_name', ''),
            wikidata_id=p.get('wikidata_id'),
            name=p.get('name', ''),
            proficiencyScore=p.get('proficiencyScore', 0.0),
            credibilityBadge=p.get('credibilityBadge', 'Unverified'),
            verificationBadge=p.get('verificationBadge'),
            scoreBreakdown=breakdown,
            reasoning=p.get('reasoning', ''),
            editorialDecision=p.get('editorialDecision', ''),
            authorityLevel=p.get('authorityLevel', 'low'),
            journalisticRelevance=p.get('journalisticRelevance', 'medium'),
            criteria_scores=p.get('criteria_scores', {})
        ))
    
    return ProficiencyResult(
        scored_people=scored_people,
        summary=data.get('summary', {})
    )


def load_and_adapt_json(file_path: Path, adapter_func) -> Any:
    """Load JSON file and adapt to typed model"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return adapter_func(data)
