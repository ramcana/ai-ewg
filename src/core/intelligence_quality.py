"""
Quality gates and fail-soft mechanisms for intelligence chain

Implements validation and fallback strategies to ensure graceful degradation
rather than hard failures.
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from .intelligence_models import (
    DiarizationResult, EntitiesResult, ResolutionResult, ProficiencyResult,
    StepWarning
)
from .logging import get_logger

logger = get_logger('pipeline.intelligence_quality')


class QualityLevel(Enum):
    """Quality assessment levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    FAILED = "failed"


class QualityGate:
    """Base class for quality gates"""
    
    def __init__(self, name: str, severity: str = "warning"):
        self.name = name
        self.severity = severity  # "info", "warning", "error"
    
    def check(self, result: Any) -> Tuple[bool, QualityLevel, List[str]]:
        """
        Check quality gate
        
        Returns:
            Tuple of (passed, quality_level, issues)
        """
        raise NotImplementedError


class DiarizationQualityGate(QualityGate):
    """Quality gate for diarization results"""
    
    def __init__(self):
        super().__init__("diarization_quality", severity="warning")
    
    def check(self, result: DiarizationResult) -> Tuple[bool, QualityLevel, List[str]]:
        """Check diarization quality"""
        issues = []
        
        # Check minimum segments
        if len(result.segments) < 5:
            issues.append("Too few segments detected (< 5) - possible diarization failure")
        
        # Check speaker count
        if result.num_speakers < 2:
            issues.append("Only one speaker detected - expected conversation")
        elif result.num_speakers > 10:
            issues.append(f"Unusually high speaker count ({result.num_speakers}) - possible over-segmentation")
        
        # Check validation if available
        if result.validation:
            if not result.validation.get('valid', True):
                validation_issues = result.validation.get('issues', [])
                issues.extend(validation_issues)
            
            quality_score = result.validation.get('quality_score', 1.0)
            if quality_score < 0.5:
                issues.append(f"Low quality score: {quality_score:.2f}")
        
        # Check consistency if available
        if result.consistency:
            if not result.consistency.get('consistent', True):
                consistency_issues = result.consistency.get('issues', [])
                issues.extend(consistency_issues)
        
        # Determine quality level
        if len(issues) == 0:
            quality_level = QualityLevel.EXCELLENT
        elif len(issues) <= 2:
            quality_level = QualityLevel.GOOD
        elif len(issues) <= 4:
            quality_level = QualityLevel.ACCEPTABLE
        else:
            quality_level = QualityLevel.DEGRADED
        
        # Always pass (fail-soft) but report issues
        passed = True
        
        return passed, quality_level, issues


class EntitiesQualityGate(QualityGate):
    """Quality gate for entity extraction results"""
    
    def __init__(self, min_candidates: int = 1):
        super().__init__("entities_quality", severity="warning")
        self.min_candidates = min_candidates
    
    def check(self, result: EntitiesResult) -> Tuple[bool, QualityLevel, List[str]]:
        """Check entity extraction quality"""
        issues = []
        
        # Check minimum candidates
        if len(result.candidates) < self.min_candidates:
            issues.append(f"Too few candidates extracted ({len(result.candidates)} < {self.min_candidates})")
        
        # Check confidence distribution
        if result.candidates:
            avg_confidence = sum(c.confidence for c in result.candidates) / len(result.candidates)
            if avg_confidence < 0.5:
                issues.append(f"Low average confidence: {avg_confidence:.2f}")
            
            high_conf_count = sum(1 for c in result.candidates if c.confidence >= 0.7)
            if high_conf_count == 0:
                issues.append("No high-confidence candidates (>= 0.7)")
        
        # Check journalistic relevance
        if result.candidates:
            high_relevance = sum(1 for c in result.candidates if c.journalistic_relevance == "high")
            if high_relevance == 0:
                issues.append("No high-relevance candidates for journalistic standards")
        
        # Check topics
        if len(result.topics) < 3:
            issues.append(f"Few topics extracted ({len(result.topics)}) - may affect context")
        
        # Determine quality level
        if len(issues) == 0:
            quality_level = QualityLevel.EXCELLENT
        elif len(issues) <= 2:
            quality_level = QualityLevel.GOOD
        elif len(issues) <= 3:
            quality_level = QualityLevel.ACCEPTABLE
        else:
            quality_level = QualityLevel.DEGRADED
        
        # Pass if we have at least some candidates
        passed = len(result.candidates) > 0
        
        return passed, quality_level, issues


class DisambiguationQualityGate(QualityGate):
    """Quality gate for disambiguation results"""
    
    def __init__(self, min_success_rate: float = 0.3):
        super().__init__("disambiguation_quality", severity="warning")
        self.min_success_rate = min_success_rate
    
    def check(self, result: ResolutionResult) -> Tuple[bool, QualityLevel, List[str]]:
        """Check disambiguation quality"""
        issues = []
        
        # Check success rate
        success_rate = result.summary.get('success_rate', 0)
        if success_rate < self.min_success_rate:
            issues.append(f"Low disambiguation success rate: {success_rate:.1%}")
        
        # Check enriched count
        if len(result.enriched_people) == 0:
            issues.append("No entities successfully disambiguated")
        
        # Check confidence distribution
        if result.enriched_people:
            avg_confidence = sum(p.confidence for p in result.enriched_people) / len(result.enriched_people)
            if avg_confidence < 0.6:
                issues.append(f"Low average confidence: {avg_confidence:.2f}")
        
        # Check authority verification
        authority_stats = result.summary.get('authority_verification', {})
        verified_count = authority_stats.get('verified_sources', 0)
        if result.enriched_people and verified_count == 0:
            issues.append("No authority-verified sources found")
        
        # Determine quality level
        if len(issues) == 0 and success_rate >= 0.7:
            quality_level = QualityLevel.EXCELLENT
        elif len(issues) <= 1 and success_rate >= 0.5:
            quality_level = QualityLevel.GOOD
        elif len(issues) <= 2 and success_rate >= 0.3:
            quality_level = QualityLevel.ACCEPTABLE
        elif success_rate >= 0.1:
            quality_level = QualityLevel.DEGRADED
        else:
            quality_level = QualityLevel.FAILED
        
        # Pass if we have at least some enriched people
        passed = len(result.enriched_people) > 0
        
        return passed, quality_level, issues


class ProficiencyQualityGate(QualityGate):
    """Quality gate for proficiency scoring results"""
    
    def __init__(self, min_verified_experts: int = 0):
        super().__init__("proficiency_quality", severity="info")
        self.min_verified_experts = min_verified_experts
    
    def check(self, result: ProficiencyResult) -> Tuple[bool, QualityLevel, List[str]]:
        """Check proficiency scoring quality"""
        issues = []
        
        # Check scored count
        if len(result.scored_people) == 0:
            issues.append("No people scored")
        
        # Check for verified experts
        verified_experts = result.summary.get('verified_experts', 0)
        if verified_experts < self.min_verified_experts:
            issues.append(f"Few verified experts ({verified_experts})")
        
        # Check score distribution
        if result.scored_people:
            avg_score = result.summary.get('avg_score', 0)
            if avg_score < 0.4:
                issues.append(f"Low average proficiency score: {avg_score:.2f}")
            
            high_score_count = sum(1 for p in result.scored_people if p.proficiencyScore >= 0.7)
            if high_score_count == 0:
                issues.append("No high-scoring individuals (>= 0.7)")
        
        # Determine quality level
        if len(issues) == 0:
            quality_level = QualityLevel.EXCELLENT
        elif len(issues) <= 1:
            quality_level = QualityLevel.GOOD
        elif len(issues) <= 2:
            quality_level = QualityLevel.ACCEPTABLE
        else:
            quality_level = QualityLevel.DEGRADED
        
        # Always pass (scoring is informational)
        passed = True
        
        return passed, quality_level, issues


class QualityGateManager:
    """Manages quality gates for intelligence chain"""
    
    def __init__(self):
        self.gates: Dict[str, QualityGate] = {
            'diarization': DiarizationQualityGate(),
            'extract_entities': EntitiesQualityGate(),
            'disambiguate': DisambiguationQualityGate(),
            'score_people': ProficiencyQualityGate()
        }
        self.logger = logger
    
    def check_step(self, step_name: str, result: Any) -> Tuple[bool, QualityLevel, List[StepWarning]]:
        """
        Check quality gate for a step
        
        Returns:
            Tuple of (passed, quality_level, warnings)
        """
        gate = self.gates.get(step_name)
        if not gate:
            # No gate defined, pass by default
            return True, QualityLevel.GOOD, []
        
        try:
            passed, quality_level, issues = gate.check(result)
            
            # Convert issues to warnings
            warnings = []
            for issue in issues:
                warnings.append(StepWarning(
                    step_name=step_name,
                    severity=gate.severity,
                    message=issue
                ))
            
            if not passed:
                self.logger.warning(
                    f"Quality gate failed: {step_name}",
                    quality_level=quality_level.value,
                    issues=issues
                )
            elif quality_level in [QualityLevel.DEGRADED, QualityLevel.ACCEPTABLE]:
                self.logger.warning(
                    f"Quality gate passed with issues: {step_name}",
                    quality_level=quality_level.value,
                    issues=issues
                )
            else:
                self.logger.info(
                    f"Quality gate passed: {step_name}",
                    quality_level=quality_level.value
                )
            
            return passed, quality_level, warnings
        
        except Exception as e:
            self.logger.error(f"Quality gate check failed: {e}")
            return True, QualityLevel.ACCEPTABLE, []
    
    def get_fallback_strategy(self, step_name: str, quality_level: QualityLevel) -> Optional[str]:
        """
        Get fallback strategy for degraded quality
        
        Returns:
            Fallback strategy description or None
        """
        if quality_level == QualityLevel.FAILED:
            if step_name == 'diarization':
                return "Use mono-speaker fallback with warning"
            elif step_name == 'extract_entities':
                return "Try spaCy fallback if LLM failed"
            elif step_name == 'disambiguate':
                return "Publish with unverified badges"
        
        elif quality_level == QualityLevel.DEGRADED:
            if step_name == 'diarization':
                return "Continue but flag for manual review"
            elif step_name == 'extract_entities':
                return "Continue with low-confidence entities marked"
            elif step_name == 'disambiguate':
                return "Continue with partial enrichment"
        
        return None
    
    def generate_quality_report(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall quality report for chain execution"""
        report = {
            'overall_quality': QualityLevel.EXCELLENT.value,
            'steps': {},
            'recommendations': []
        }
        
        worst_quality = QualityLevel.EXCELLENT
        
        for step_name, result in results.items():
            passed, quality_level, warnings = self.check_step(step_name, result)
            
            report['steps'][step_name] = {
                'passed': passed,
                'quality_level': quality_level.value,
                'issues': [w.message for w in warnings]
            }
            
            # Track worst quality
            quality_order = [
                QualityLevel.EXCELLENT,
                QualityLevel.GOOD,
                QualityLevel.ACCEPTABLE,
                QualityLevel.DEGRADED,
                QualityLevel.FAILED
            ]
            
            if quality_order.index(quality_level) > quality_order.index(worst_quality):
                worst_quality = quality_level
            
            # Add fallback strategy if needed
            if quality_level in [QualityLevel.DEGRADED, QualityLevel.FAILED]:
                strategy = self.get_fallback_strategy(step_name, quality_level)
                if strategy:
                    report['recommendations'].append({
                        'step': step_name,
                        'strategy': strategy
                    })
        
        report['overall_quality'] = worst_quality.value
        
        return report
