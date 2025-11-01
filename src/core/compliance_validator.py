"""
Rights and Compliance Validation for Social Media Packages

Implements rights metadata validation, content policy compliance,
age restriction handling, and accessibility validation with caption requirements.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set
from enum import Enum

from .platform_profiles import PlatformProfile
from .publishing_models import (
    SocialPackage, RightsMetadata, UploadManifest, MediaAsset, AssetType,
    ValidationResult, ValidationError, ValidationWarning, ErrorType, Severity
)


class ContentRating(Enum):
    """Content rating classifications"""
    GENERAL = "general"
    TEEN = "teen"
    MATURE = "mature"
    ADULT = "adult"


class ComplianceLevel(Enum):
    """Compliance validation levels"""
    STRICT = "strict"      # Zero tolerance for violations
    STANDARD = "standard"  # Allow warnings but block errors
    PERMISSIVE = "permissive"  # Allow most content with warnings


@dataclass
class ContentPolicyRule:
    """Content policy rule definition"""
    rule_id: str
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    severity: Severity = Severity.WARNING
    platforms: List[str] = field(default_factory=list)  # Empty = all platforms
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rule_id': self.rule_id,
            'name': self.name,
            'description': self.description,
            'keywords': self.keywords,
            'patterns': self.patterns,
            'severity': self.severity.value,
            'platforms': self.platforms
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentPolicyRule':
        return cls(
            rule_id=data['rule_id'],
            name=data['name'],
            description=data['description'],
            keywords=data.get('keywords', []),
            patterns=data.get('patterns', []),
            severity=Severity(data.get('severity', 'warning')),
            platforms=data.get('platforms', [])
        )


@dataclass
class ComplianceViolation:
    """Content policy violation details"""
    rule_id: str
    rule_name: str
    violation_type: str
    message: str
    location: str
    severity: Severity
    matched_content: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'violation_type': self.violation_type,
            'message': self.message,
            'location': self.location,
            'severity': self.severity.value,
            'matched_content': self.matched_content
        }


@dataclass
class ComplianceReport:
    """Comprehensive compliance validation report"""
    is_compliant: bool
    content_rating: ContentRating
    violations: List[ComplianceViolation] = field(default_factory=list)
    rights_issues: List[str] = field(default_factory=list)
    accessibility_issues: List[str] = field(default_factory=list)
    platform_specific_issues: Dict[str, List[str]] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_compliant': self.is_compliant,
            'content_rating': self.content_rating.value,
            'violations': [v.to_dict() for v in self.violations],
            'rights_issues': self.rights_issues,
            'accessibility_issues': self.accessibility_issues,
            'platform_specific_issues': self.platform_specific_issues,
            'recommendations': self.recommendations
        }


class RightsValidator:
    """Validates rights metadata and licensing compliance"""
    
    def __init__(self, compliance_level: ComplianceLevel = ComplianceLevel.STANDARD):
        """
        Initialize rights validator
        
        Args:
            compliance_level: Validation strictness level
        """
        self.compliance_level = compliance_level
    
    def validate_rights_metadata(self, rights: RightsMetadata, platform_id: str) -> ValidationResult:
        """
        Validate rights metadata for platform compliance
        
        Args:
            rights: Rights metadata to validate
            platform_id: Target platform identifier
            
        Returns:
            ValidationResult with rights validation details
        """
        errors = []
        warnings = []
        
        # Validate music clearance
        music_result = self._validate_music_clearance(rights, platform_id)
        errors.extend(music_result.errors)
        warnings.extend(music_result.warnings)
        
        # Validate third-party assets
        assets_result = self._validate_third_party_assets(rights, platform_id)
        errors.extend(assets_result.errors)
        warnings.extend(assets_result.warnings)
        
        # Validate copyright information
        copyright_result = self._validate_copyright_info(rights)
        errors.extend(copyright_result.errors)
        warnings.extend(copyright_result.warnings)
        
        # Validate licensing
        license_result = self._validate_licensing(rights)
        errors.extend(license_result.errors)
        warnings.extend(license_result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'platform': platform_id, 'compliance_level': self.compliance_level.value}
        )
    
    def _validate_music_clearance(self, rights: RightsMetadata, platform_id: str) -> ValidationResult:
        """Validate music clearance requirements"""
        errors = []
        warnings = []
        
        # Platforms with strict music policies
        strict_music_platforms = ['youtube', 'instagram', 'tiktok', 'facebook']
        
        if platform_id in strict_music_platforms:
            if not rights.music_clearance:
                if self.compliance_level == ComplianceLevel.STRICT:
                    errors.append(ValidationError(
                        error_type=ErrorType.RIGHTS_VALIDATION,
                        message=f"Music clearance required for {platform_id}",
                        location="rights.music_clearance",
                        severity=Severity.ERROR
                    ))
                else:
                    warnings.append(ValidationError(
                        error_type=ErrorType.RIGHTS_VALIDATION,
                        message=f"Music clearance not confirmed for {platform_id} - may result in content claims",
                        location="rights.music_clearance",
                        severity=Severity.WARNING
                    ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_third_party_assets(self, rights: RightsMetadata, platform_id: str) -> ValidationResult:
        """Validate third-party asset usage"""
        errors = []
        warnings = []
        
        if rights.third_party_assets:
            # Check for problematic asset types
            problematic_assets = ['stock_footage', 'copyrighted_images', 'branded_content']
            
            for asset in rights.third_party_assets:
                if any(prob in asset.lower() for prob in problematic_assets):
                    if self.compliance_level == ComplianceLevel.STRICT:
                        errors.append(ValidationError(
                            error_type=ErrorType.RIGHTS_VALIDATION,
                            message=f"Potentially problematic third-party asset: {asset}",
                            location="rights.third_party_assets",
                            severity=Severity.ERROR
                        ))
                    else:
                        warnings.append(ValidationError(
                            error_type=ErrorType.RIGHTS_VALIDATION,
                            message=f"Review required for third-party asset: {asset}",
                            location="rights.third_party_assets",
                            severity=Severity.WARNING
                        ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_copyright_info(self, rights: RightsMetadata) -> ValidationResult:
        """Validate copyright holder information"""
        errors = []
        warnings = []
        
        if not rights.copyright_holder:
            if self.compliance_level == ComplianceLevel.STRICT:
                errors.append(ValidationError(
                    error_type=ErrorType.RIGHTS_VALIDATION,
                    message="Copyright holder must be specified",
                    location="rights.copyright_holder",
                    severity=Severity.ERROR
                ))
            else:
                warnings.append(ValidationError(
                    error_type=ErrorType.RIGHTS_VALIDATION,
                    message="Copyright holder not specified",
                    location="rights.copyright_holder",
                    severity=Severity.WARNING
                ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_licensing(self, rights: RightsMetadata) -> ValidationResult:
        """Validate licensing information"""
        errors = []
        warnings = []
        
        # Check for valid license URL if provided
        if rights.license_url:
            # Basic URL validation
            if not rights.license_url.startswith(('http://', 'https://')):
                errors.append(ValidationError(
                    error_type=ErrorType.RIGHTS_VALIDATION,
                    message="Invalid license URL format",
                    location="rights.license_url",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


class ContentPolicyValidator:
    """Validates content against platform policies and community guidelines"""
    
    def __init__(self, compliance_level: ComplianceLevel = ComplianceLevel.STANDARD):
        """
        Initialize content policy validator
        
        Args:
            compliance_level: Validation strictness level
        """
        self.compliance_level = compliance_level
        self.policy_rules = self._load_default_policy_rules()
    
    def validate_content_policy(self, 
                               upload_manifest: UploadManifest, 
                               platform_id: str) -> ComplianceReport:
        """
        Validate content against platform policies
        
        Args:
            upload_manifest: Upload manifest with content metadata
            platform_id: Target platform identifier
            
        Returns:
            ComplianceReport with policy validation results
        """
        violations = []
        
        # Validate title
        title_violations = self._check_content_violations(
            upload_manifest.title, "title", platform_id
        )
        violations.extend(title_violations)
        
        # Validate description
        desc_violations = self._check_content_violations(
            upload_manifest.description, "description", platform_id
        )
        violations.extend(desc_violations)
        
        # Validate tags
        for i, tag in enumerate(upload_manifest.tags):
            tag_violations = self._check_content_violations(
                tag, f"tags[{i}]", platform_id
            )
            violations.extend(tag_violations)
        
        # Determine content rating
        content_rating = self._determine_content_rating(upload_manifest)
        
        # Check age restriction compliance
        age_violations = self._validate_age_restrictions(upload_manifest, platform_id)
        violations.extend(age_violations)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(violations, content_rating)
        
        # Determine overall compliance
        error_violations = [v for v in violations if v.severity == Severity.ERROR]
        is_compliant = len(error_violations) == 0
        
        return ComplianceReport(
            is_compliant=is_compliant,
            content_rating=content_rating,
            violations=violations,
            recommendations=recommendations
        )
    
    def _load_default_policy_rules(self) -> List[ContentPolicyRule]:
        """Load default content policy rules"""
        return [
            ContentPolicyRule(
                rule_id="violence",
                name="Violence and Graphic Content",
                description="Content depicting violence or graphic imagery",
                keywords=["violence", "blood", "gore", "death", "killing", "murder"],
                severity=Severity.ERROR,
                platforms=["youtube", "instagram", "tiktok"]
            ),
            ContentPolicyRule(
                rule_id="hate_speech",
                name="Hate Speech",
                description="Content promoting hatred or discrimination",
                keywords=["hate", "racist", "discrimination", "bigotry"],
                patterns=[r"\b(hate|racist|discrimination)\b"],
                severity=Severity.ERROR
            ),
            ContentPolicyRule(
                rule_id="adult_content",
                name="Adult Content",
                description="Sexually explicit or adult-oriented content",
                keywords=["explicit", "adult", "sexual", "nsfw", "mature"],
                severity=Severity.WARNING,
                platforms=["youtube", "instagram"]
            ),
            ContentPolicyRule(
                rule_id="spam",
                name="Spam and Misleading Content",
                description="Spam, clickbait, or misleading content",
                keywords=["click here", "free money", "get rich quick", "miracle cure"],
                patterns=[r"!!!", r"URGENT", r"ACT NOW"],
                severity=Severity.WARNING
            ),
            ContentPolicyRule(
                rule_id="copyright",
                name="Copyright Infringement",
                description="Potential copyright infringement indicators",
                keywords=["copyrighted", "stolen", "pirated", "unauthorized"],
                severity=Severity.ERROR
            ),
            ContentPolicyRule(
                rule_id="misinformation",
                name="Misinformation",
                description="Potentially false or misleading information",
                keywords=["conspiracy", "hoax", "fake news", "debunked"],
                severity=Severity.WARNING
            )
        ]
    
    def _check_content_violations(self, 
                                 content: str, 
                                 location: str, 
                                 platform_id: str) -> List[ComplianceViolation]:
        """Check content against policy rules"""
        violations = []
        
        if not content:
            return violations
        
        content_lower = content.lower()
        
        for rule in self.policy_rules:
            # Skip rule if it doesn't apply to this platform
            if rule.platforms and platform_id not in rule.platforms:
                continue
            
            # Check keywords
            for keyword in rule.keywords:
                if keyword.lower() in content_lower:
                    violations.append(ComplianceViolation(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        violation_type="keyword_match",
                        message=f"Policy violation detected: {rule.description}",
                        location=location,
                        severity=rule.severity,
                        matched_content=keyword
                    ))
            
            # Check patterns
            for pattern in rule.patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    violations.append(ComplianceViolation(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        violation_type="pattern_match",
                        message=f"Policy violation detected: {rule.description}",
                        location=location,
                        severity=rule.severity,
                        matched_content=match.group()
                    ))
        
        return violations
    
    def _determine_content_rating(self, upload_manifest: UploadManifest) -> ContentRating:
        """Determine content rating based on metadata"""
        content_text = f"{upload_manifest.title} {upload_manifest.description} {' '.join(upload_manifest.tags)}"
        content_lower = content_text.lower()
        
        # Check for adult content indicators
        adult_keywords = ["explicit", "adult", "sexual", "nsfw", "18+", "mature"]
        if any(keyword in content_lower for keyword in adult_keywords):
            return ContentRating.ADULT
        
        # Check for mature content indicators
        mature_keywords = ["violence", "blood", "mature", "teen", "13+"]
        if any(keyword in content_lower for keyword in mature_keywords):
            return ContentRating.MATURE
        
        # Check for teen content indicators
        teen_keywords = ["teen", "young adult", "pg-13"]
        if any(keyword in content_lower for keyword in teen_keywords):
            return ContentRating.TEEN
        
        return ContentRating.GENERAL
    
    def _validate_age_restrictions(self, 
                                  upload_manifest: UploadManifest, 
                                  platform_id: str) -> List[ComplianceViolation]:
        """Validate age restriction settings"""
        violations = []
        
        # Check for conflicting age settings
        if upload_manifest.age_restriction and upload_manifest.made_for_kids:
            violations.append(ComplianceViolation(
                rule_id="age_conflict",
                rule_name="Age Restriction Conflict",
                violation_type="configuration_error",
                message="Content cannot be both age-restricted and made for kids",
                location="upload_manifest",
                severity=Severity.ERROR
            ))
        
        # Platform-specific age restriction validation
        if platform_id == "youtube":
            # YouTube requires age restriction for certain content
            content_text = f"{upload_manifest.title} {upload_manifest.description}"
            adult_indicators = ["explicit", "adult", "sexual", "mature"]
            
            if any(indicator in content_text.lower() for indicator in adult_indicators):
                if not upload_manifest.age_restriction:
                    violations.append(ComplianceViolation(
                        rule_id="youtube_age_restriction",
                        rule_name="YouTube Age Restriction Required",
                        violation_type="platform_policy",
                        message="Content appears to require age restriction on YouTube",
                        location="upload_manifest.age_restriction",
                        severity=Severity.WARNING
                    ))
        
        return violations
    
    def _generate_recommendations(self, 
                                violations: List[ComplianceViolation], 
                                content_rating: ContentRating) -> List[str]:
        """Generate recommendations based on violations and content rating"""
        recommendations = []
        
        # Recommendations based on violations
        violation_types = {v.rule_id for v in violations}
        
        if "violence" in violation_types:
            recommendations.append("Consider adding content warnings for violent content")
            recommendations.append("Review platform-specific violence policies")
        
        if "adult_content" in violation_types:
            recommendations.append("Enable age restriction for adult content")
            recommendations.append("Consider platform content guidelines for mature themes")
        
        if "hate_speech" in violation_types:
            recommendations.append("Review content for potentially offensive language")
            recommendations.append("Consider community guidelines compliance")
        
        # Recommendations based on content rating
        if content_rating == ContentRating.ADULT:
            recommendations.append("Enable age restriction for adult content")
            recommendations.append("Consider platform monetization restrictions")
        
        elif content_rating == ContentRating.MATURE:
            recommendations.append("Consider age restriction for mature content")
            recommendations.append("Add appropriate content warnings")
        
        return recommendations


class AccessibilityValidator:
    """Validates accessibility compliance including caption requirements"""
    
    def __init__(self, compliance_level: ComplianceLevel = ComplianceLevel.STANDARD):
        """
        Initialize accessibility validator
        
        Args:
            compliance_level: Validation strictness level
        """
        self.compliance_level = compliance_level
    
    def validate_accessibility(self, 
                              social_package: SocialPackage, 
                              platform_profile: PlatformProfile) -> ValidationResult:
        """
        Validate accessibility compliance for social package
        
        Args:
            social_package: Social package to validate
            platform_profile: Platform profile with accessibility requirements
            
        Returns:
            ValidationResult with accessibility validation details
        """
        errors = []
        warnings = []
        
        # Validate caption requirements
        caption_result = self._validate_captions(social_package, platform_profile)
        errors.extend(caption_result.errors)
        warnings.extend(caption_result.warnings)
        
        # Validate thumbnail accessibility
        thumbnail_result = self._validate_thumbnails(social_package, platform_profile)
        errors.extend(thumbnail_result.errors)
        warnings.extend(thumbnail_result.warnings)
        
        # Validate metadata accessibility
        metadata_result = self._validate_metadata_accessibility(social_package.upload_manifest)
        errors.extend(metadata_result.errors)
        warnings.extend(metadata_result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'platform': platform_profile.platform_id}
        )
    
    def _validate_captions(self, 
                          social_package: SocialPackage, 
                          platform_profile: PlatformProfile) -> ValidationResult:
        """Validate caption requirements"""
        errors = []
        warnings = []
        
        # Check if video content exists
        video_assets = [asset for asset in social_package.media_assets if asset.asset_type == AssetType.VIDEO]
        if not video_assets:
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
        
        # Check caption requirements
        caption_assets = [asset for asset in social_package.media_assets if asset.asset_type == AssetType.CAPTIONS]
        
        if platform_profile.metadata.supports_captions:
            # Platform supports separate captions
            if not caption_assets and not social_package.upload_manifest.captions_url:
                if self.compliance_level == ComplianceLevel.STRICT:
                    errors.append(ValidationError(
                        error_type=ErrorType.PLATFORM_COMPLIANCE,
                        message="Captions required for accessibility compliance",
                        location="media_assets.captions",
                        severity=Severity.ERROR
                    ))
                else:
                    warnings.append(ValidationError(
                        error_type=ErrorType.PLATFORM_COMPLIANCE,
                        message="Captions recommended for accessibility",
                        location="media_assets.captions",
                        severity=Severity.WARNING
                    ))
        else:
            # Platform requires burned-in captions
            if not self._has_burned_captions(video_assets):
                if self.compliance_level == ComplianceLevel.STRICT:
                    errors.append(ValidationError(
                        error_type=ErrorType.PLATFORM_COMPLIANCE,
                        message="Burned-in captions required for this platform",
                        location="media_assets.video",
                        severity=Severity.ERROR
                    ))
                else:
                    warnings.append(ValidationError(
                        error_type=ErrorType.PLATFORM_COMPLIANCE,
                        message="Burned-in captions recommended for accessibility",
                        location="media_assets.video",
                        severity=Severity.WARNING
                    ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_thumbnails(self, 
                           social_package: SocialPackage, 
                           platform_profile: PlatformProfile) -> ValidationResult:
        """Validate thumbnail accessibility"""
        errors = []
        warnings = []
        
        if not platform_profile.metadata.supports_thumbnails:
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
        
        # Check for thumbnail presence
        thumbnail_assets = [asset for asset in social_package.media_assets if asset.asset_type == AssetType.THUMBNAIL]
        
        if not thumbnail_assets and not social_package.upload_manifest.thumbnail_url:
            warnings.append(ValidationError(
                error_type=ErrorType.PLATFORM_COMPLIANCE,
                message="Thumbnail recommended for better accessibility and discoverability",
                location="media_assets.thumbnail",
                severity=Severity.WARNING
            ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_metadata_accessibility(self, upload_manifest: UploadManifest) -> ValidationResult:
        """Validate metadata for accessibility"""
        errors = []
        warnings = []
        
        # Check for descriptive title
        if not upload_manifest.title or len(upload_manifest.title.strip()) < 5:
            warnings.append(ValidationError(
                error_type=ErrorType.PLATFORM_COMPLIANCE,
                message="Descriptive title recommended for accessibility",
                location="upload_manifest.title",
                severity=Severity.WARNING
            ))
        
        # Check for descriptive description
        if not upload_manifest.description or len(upload_manifest.description.strip()) < 20:
            warnings.append(ValidationError(
                error_type=ErrorType.PLATFORM_COMPLIANCE,
                message="Detailed description recommended for accessibility",
                location="upload_manifest.description",
                severity=Severity.WARNING
            ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _has_burned_captions(self, video_assets: List[MediaAsset]) -> bool:
        """Check if video has burned-in captions (heuristic)"""
        # This is a simplified check - in practice, you might analyze the video
        # or check for specific naming conventions indicating captioned versions
        for asset in video_assets:
            if "captioned" in Path(asset.asset_path).name.lower():
                return True
        return False


class ComplianceValidator:
    """Main compliance validator combining all validation components"""
    
    def __init__(self, compliance_level: ComplianceLevel = ComplianceLevel.STANDARD):
        """
        Initialize compliance validator
        
        Args:
            compliance_level: Validation strictness level
        """
        self.compliance_level = compliance_level
        self.rights_validator = RightsValidator(compliance_level)
        self.policy_validator = ContentPolicyValidator(compliance_level)
        self.accessibility_validator = AccessibilityValidator(compliance_level)
    
    def validate_social_package_compliance(self, 
                                         social_package: SocialPackage,
                                         platform_profile: PlatformProfile) -> ComplianceReport:
        """
        Perform comprehensive compliance validation
        
        Args:
            social_package: Social package to validate
            platform_profile: Platform profile with requirements
            
        Returns:
            ComplianceReport with all validation results
        """
        # Validate rights
        rights_result = self.rights_validator.validate_rights_metadata(
            social_package.rights, platform_profile.platform_id
        )
        
        # Validate content policy
        policy_report = self.policy_validator.validate_content_policy(
            social_package.upload_manifest, platform_profile.platform_id
        )
        
        # Validate accessibility
        accessibility_result = self.accessibility_validator.validate_accessibility(
            social_package, platform_profile
        )
        
        # Combine results
        all_violations = policy_report.violations.copy()
        
        # Convert rights validation errors to violations
        for error in rights_result.errors:
            all_violations.append(ComplianceViolation(
                rule_id="rights_validation",
                rule_name="Rights Validation",
                violation_type="rights_error",
                message=error.message,
                location=error.location,
                severity=error.severity
            ))
        
        # Convert accessibility validation errors to violations
        for error in accessibility_result.errors:
            all_violations.append(ComplianceViolation(
                rule_id="accessibility_validation",
                rule_name="Accessibility Validation",
                violation_type="accessibility_error",
                message=error.message,
                location=error.location,
                severity=error.severity
            ))
        
        # Collect issues by category
        rights_issues = [error.message for error in rights_result.errors + rights_result.warnings]
        accessibility_issues = [error.message for error in accessibility_result.errors + accessibility_result.warnings]
        
        # Determine overall compliance
        error_violations = [v for v in all_violations if v.severity == Severity.ERROR]
        is_compliant = len(error_violations) == 0
        
        # Generate comprehensive recommendations
        recommendations = policy_report.recommendations.copy()
        if rights_issues:
            recommendations.append("Review rights and licensing documentation")
        if accessibility_issues:
            recommendations.append("Improve accessibility features (captions, descriptions)")
        
        return ComplianceReport(
            is_compliant=is_compliant,
            content_rating=policy_report.content_rating,
            violations=all_violations,
            rights_issues=rights_issues,
            accessibility_issues=accessibility_issues,
            platform_specific_issues={platform_profile.platform_id: [v.message for v in all_violations]},
            recommendations=recommendations
        )


def create_compliance_validator(compliance_level: ComplianceLevel = ComplianceLevel.STANDARD) -> ComplianceValidator:
    """
    Factory function to create compliance validator
    
    Args:
        compliance_level: Validation strictness level
        
    Returns:
        ComplianceValidator instance
    """
    return ComplianceValidator(compliance_level)