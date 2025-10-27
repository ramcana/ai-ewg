"""
Social Media Package Validation Component

Implements platform-specific formatting validation for social media packages
including character limits, hashtag limits, and content compliance checks.
"""

import streamlit as st
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation issue severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Validation issue details"""
    severity: ValidationSeverity
    message: str
    field: str
    current_value: Any
    expected_value: Optional[Any] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Social package validation result"""
    is_valid: bool
    platform: str
    issues: List[ValidationIssue]
    score: float  # 0-100 validation score
    
    @property
    def errors(self) -> List[ValidationIssue]:
        """Get error-level issues"""
        return [issue for issue in self.issues if issue.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get warning-level issues"""
        return [issue for issue in self.issues if issue.severity == ValidationSeverity.WARNING]
    
    @property
    def infos(self) -> List[ValidationIssue]:
        """Get info-level issues"""
        return [issue for issue in self.issues if issue.severity == ValidationSeverity.INFO]


class SocialPackageValidator:
    """
    Social media package validator for platform-specific formatting
    
    Validates social media packages against platform requirements including
    character limits, hashtag limits, content guidelines, and best practices.
    """
    
    def __init__(self):
        """Initialize social package validator"""
        # Platform-specific validation rules
        self.platform_rules = {
            'twitter': {
                'char_limit': 280,
                'hashtag_limit': 2,  # Recommended for better engagement
                'hashtag_max': 10,   # Technical limit
                'optimal_length': 100,  # Optimal tweet length for engagement
                'media_limit': 4,
                'video_duration_limit': 140,  # seconds
                'best_practices': {
                    'use_mentions': True,
                    'include_cta': False,  # Call-to-action not always needed
                    'optimal_hashtags': 1,
                    'avoid_all_caps': True
                }
            },
            'instagram': {
                'char_limit': 2200,
                'hashtag_limit': 30,
                'hashtag_max': 30,
                'optimal_length': 125,  # Optimal caption length
                'media_limit': 10,
                'video_duration_limit': 60,  # seconds for reels
                'best_practices': {
                    'use_emojis': True,
                    'include_cta': True,
                    'optimal_hashtags': 11,
                    'line_breaks': True
                }
            },
            'tiktok': {
                'char_limit': 150,
                'hashtag_limit': 10,  # Recommended
                'hashtag_max': 100,   # Technical limit
                'optimal_length': 100,
                'media_limit': 1,
                'video_duration_limit': 180,  # seconds
                'best_practices': {
                    'use_trending_hashtags': True,
                    'include_cta': True,
                    'optimal_hashtags': 3,
                    'use_emojis': True
                }
            },
            'facebook': {
                'char_limit': 63206,
                'hashtag_limit': 10,  # Recommended
                'hashtag_max': 30,    # Practical limit
                'optimal_length': 80,  # Optimal post length
                'media_limit': 10,
                'video_duration_limit': 240,  # seconds
                'best_practices': {
                    'include_cta': True,
                    'use_questions': True,
                    'optimal_hashtags': 2,
                    'storytelling': True
                }
            }
        }
    
    def validate_package(self, package_data: Dict[str, Any], platform: str) -> ValidationResult:
        """
        Validate complete social media package
        
        Args:
            package_data: Social package data dictionary
            platform: Target platform
            
        Returns:
            ValidationResult: Comprehensive validation results
        """
        issues = []
        
        if platform not in self.platform_rules:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Unsupported platform: {platform}",
                field="platform",
                current_value=platform
            ))
            return ValidationResult(
                is_valid=False,
                platform=platform,
                issues=issues,
                score=0.0
            )
        
        rules = self.platform_rules[platform]
        
        # Validate caption
        caption_issues = self._validate_caption(package_data.get('caption', ''), platform, rules)
        issues.extend(caption_issues)
        
        # Validate hashtags
        hashtag_issues = self._validate_hashtags(package_data.get('hashtags', []), platform, rules)
        issues.extend(hashtag_issues)
        
        # Validate media files
        media_issues = self._validate_media_files(package_data.get('media_files', []), platform, rules)
        issues.extend(media_issues)
        
        # Validate best practices
        best_practice_issues = self._validate_best_practices(package_data, platform, rules)
        issues.extend(best_practice_issues)
        
        # Calculate validation score
        score = self._calculate_validation_score(issues)
        
        # Determine if package is valid (no errors)
        is_valid = len([issue for issue in issues if issue.severity == ValidationSeverity.ERROR]) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            platform=platform,
            issues=issues,
            score=score
        )
    
    def _validate_caption(self, caption: str, platform: str, rules: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate caption content and length"""
        issues = []
        
        # Character limit validation
        char_limit = rules['char_limit']
        caption_length = len(caption)
        
        if caption_length > char_limit:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Caption exceeds {platform} character limit",
                field="caption",
                current_value=caption_length,
                expected_value=char_limit,
                suggestion=f"Reduce caption by {caption_length - char_limit} characters"
            ))
        elif caption_length > char_limit * 0.9:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"Caption is close to {platform} character limit",
                field="caption",
                current_value=caption_length,
                expected_value=char_limit,
                suggestion="Consider shortening for safety margin"
            ))
        
        # Optimal length validation
        optimal_length = rules.get('optimal_length', char_limit // 2)
        if platform in ['twitter', 'facebook'] and caption_length > optimal_length * 2:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                message=f"Caption longer than optimal for {platform} engagement",
                field="caption",
                current_value=caption_length,
                expected_value=optimal_length,
                suggestion=f"Consider shortening to ~{optimal_length} characters for better engagement"
            ))
        
        # Content validation
        if not caption.strip():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Caption cannot be empty",
                field="caption",
                current_value="",
                suggestion="Add meaningful caption content"
            ))
        
        # Platform-specific content checks
        if platform == 'twitter':
            # Check for excessive capitalization
            if rules['best_practices']['avoid_all_caps'] and caption.isupper():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Avoid using all caps on Twitter",
                    field="caption",
                    current_value="ALL CAPS",
                    suggestion="Use normal capitalization for better engagement"
                ))
        
        elif platform == 'instagram':
            # Check for line breaks (good for readability)
            if rules['best_practices']['line_breaks'] and '\n' not in caption and len(caption) > 200:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    message="Consider adding line breaks for better readability",
                    field="caption",
                    current_value="No line breaks",
                    suggestion="Add line breaks to improve visual appeal"
                ))
        
        return issues
    
    def _validate_hashtags(self, hashtags: List[str], platform: str, rules: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate hashtag count and format"""
        issues = []
        
        hashtag_count = len(hashtags)
        hashtag_limit = rules['hashtag_limit']
        hashtag_max = rules['hashtag_max']
        
        # Count validation
        if hashtag_count > hashtag_max:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Too many hashtags for {platform}",
                field="hashtags",
                current_value=hashtag_count,
                expected_value=hashtag_max,
                suggestion=f"Remove {hashtag_count - hashtag_max} hashtags"
            ))
        elif hashtag_count > hashtag_limit:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"More hashtags than recommended for {platform}",
                field="hashtags",
                current_value=hashtag_count,
                expected_value=hashtag_limit,
                suggestion=f"Consider reducing to {hashtag_limit} hashtags for better engagement"
            ))
        
        # Optimal count validation
        optimal_hashtags = rules['best_practices'].get('optimal_hashtags', hashtag_limit)
        if hashtag_count < optimal_hashtags // 2:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                message=f"Consider adding more hashtags for {platform}",
                field="hashtags",
                current_value=hashtag_count,
                expected_value=optimal_hashtags,
                suggestion=f"Add {optimal_hashtags - hashtag_count} more relevant hashtags"
            ))
        
        # Format validation
        for i, hashtag in enumerate(hashtags):
            if not hashtag.startswith('#'):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Hashtag must start with #",
                    field=f"hashtags[{i}]",
                    current_value=hashtag,
                    suggestion=f"Change '{hashtag}' to '#{hashtag}'"
                ))
            
            # Length validation
            if len(hashtag) > 30:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Hashtag too long",
                    field=f"hashtags[{i}]",
                    current_value=len(hashtag),
                    expected_value=30,
                    suggestion="Shorten hashtag for better usability"
                ))
            
            # Character validation
            if not hashtag[1:].replace('_', '').isalnum():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Hashtag contains special characters",
                    field=f"hashtags[{i}]",
                    current_value=hashtag,
                    suggestion="Use only letters, numbers, and underscores"
                ))
        
        # Duplicate validation
        unique_hashtags = set(hashtag.lower() for hashtag in hashtags)
        if len(unique_hashtags) < len(hashtags):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="Duplicate hashtags found",
                field="hashtags",
                current_value=len(hashtags) - len(unique_hashtags),
                suggestion="Remove duplicate hashtags"
            ))
        
        return issues
    
    def _validate_media_files(self, media_files: List[str], platform: str, rules: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate media file count and types"""
        issues = []
        
        media_count = len(media_files)
        media_limit = rules['media_limit']
        
        if media_count > media_limit:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Too many media files for {platform}",
                field="media_files",
                current_value=media_count,
                expected_value=media_limit,
                suggestion=f"Remove {media_count - media_limit} media files"
            ))
        
        # Platform-specific media validation
        if platform == 'tiktok' and media_count > 1:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="TikTok only supports single video uploads",
                field="media_files",
                current_value=media_count,
                expected_value=1,
                suggestion="Select only one video file for TikTok"
            ))
        
        return issues
    
    def _validate_best_practices(self, package_data: Dict[str, Any], platform: str, rules: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate against platform best practices"""
        issues = []
        
        best_practices = rules.get('best_practices', {})
        caption = package_data.get('caption', '')
        
        # Call-to-action validation
        if best_practices.get('include_cta', False):
            cta_keywords = ['click', 'link', 'visit', 'check out', 'learn more', 'watch', 'listen', 'read more']
            has_cta = any(keyword in caption.lower() for keyword in cta_keywords)
            
            if not has_cta:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    message=f"Consider adding a call-to-action for {platform}",
                    field="caption",
                    current_value="No CTA detected",
                    suggestion="Add phrases like 'Listen now', 'Check it out', or 'Learn more'"
                ))
        
        # Emoji usage validation
        if best_practices.get('use_emojis', False) and platform in ['instagram', 'tiktok']:
            import re
            emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF]')
            has_emojis = bool(emoji_pattern.search(caption))
            
            if not has_emojis:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    message=f"Consider adding emojis for {platform}",
                    field="caption",
                    current_value="No emojis",
                    suggestion="Add relevant emojis to increase engagement"
                ))
        
        # Question validation for Facebook
        if platform == 'facebook' and best_practices.get('use_questions', False):
            has_question = '?' in caption
            
            if not has_question:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    message="Consider adding a question to encourage engagement",
                    field="caption",
                    current_value="No questions",
                    suggestion="Add a question to encourage comments and discussion"
                ))
        
        return issues
    
    def _calculate_validation_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate validation score based on issues"""
        if not issues:
            return 100.0
        
        # Scoring weights
        error_weight = -25.0
        warning_weight = -10.0
        info_weight = -2.0
        
        score = 100.0
        
        for issue in issues:
            if issue.severity == ValidationSeverity.ERROR:
                score += error_weight
            elif issue.severity == ValidationSeverity.WARNING:
                score += warning_weight
            elif issue.severity == ValidationSeverity.INFO:
                score += info_weight
        
        return max(0.0, min(100.0, score))
    
    def render_validation_results(self, validation_result: ValidationResult) -> None:
        """
        Render validation results in Streamlit interface
        
        Args:
            validation_result: Validation results to display
        """
        platform = validation_result.platform.title()
        
        # Overall status
        if validation_result.is_valid:
            st.success(f"✅ {platform} package is valid (Score: {validation_result.score:.1f}/100)")
        else:
            st.error(f"❌ {platform} package has errors (Score: {validation_result.score:.1f}/100)")
        
        # Display issues by severity
        if validation_result.errors:
            st.markdown("**🚨 Errors (Must Fix):**")
            for error in validation_result.errors:
                st.error(f"• {error.message}")
                if error.suggestion:
                    st.caption(f"💡 Suggestion: {error.suggestion}")
        
        if validation_result.warnings:
            st.markdown("**⚠️ Warnings (Recommended):**")
            for warning in validation_result.warnings:
                st.warning(f"• {warning.message}")
                if warning.suggestion:
                    st.caption(f"💡 Suggestion: {warning.suggestion}")
        
        if validation_result.infos:
            with st.expander("💡 Optimization Tips", expanded=False):
                for info in validation_result.infos:
                    st.info(f"• {info.message}")
                    if info.suggestion:
                        st.caption(f"💡 Suggestion: {info.suggestion}")
        
        # Score visualization
        if validation_result.score < 100:
            score_color = "red" if validation_result.score < 70 else "orange" if validation_result.score < 85 else "green"
            st.markdown(f"""
            <div style="background-color: {score_color}; color: white; padding: 5px 10px; 
                       border-radius: 5px; text-align: center; margin: 10px 0;">
                Validation Score: {validation_result.score:.1f}/100
            </div>
            """, unsafe_allow_html=True)


def validate_social_package(package_data: Dict[str, Any], platform: str) -> ValidationResult:
    """
    Convenience function to validate a social media package
    
    Args:
        package_data: Social package data dictionary
        platform: Target platform
        
    Returns:
        ValidationResult: Validation results
    """
    validator = SocialPackageValidator()
    return validator.validate_package(package_data, platform)


def render_package_validation_interface(package_data: Dict[str, Any], platform: str) -> None:
    """
    Render package validation interface in Streamlit
    
    Args:
        package_data: Social package data dictionary
        platform: Target platform
    """
    validator = SocialPackageValidator()
    validation_result = validator.validate_package(package_data, platform)
    validator.render_validation_results(validation_result)