"""
Feed and Social Package Validators

Implements RSS and XML sitemap specification validation,
social package platform compliance checking, and validation
result aggregation and reporting.
"""

import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set
from urllib.parse import urlparse
import json

from .publishing_models import (
    ValidationResult, ValidationError, ValidationWarning, ErrorType, Severity,
    SocialPackage, PackageStatus, Episode, Series, Host
)
from .platform_profiles import PlatformProfile, MediaSpecValidator
from .compliance_validator import ComplianceValidator, ComplianceLevel
from .feed_generator import RSSFeed, XMLSitemap


@dataclass
class FeedValidationReport:
    """Comprehensive feed validation report"""
    feed_type: str
    is_valid: bool
    total_items: int
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    specification_compliance: Dict[str, bool] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'feed_type': self.feed_type,
            'is_valid': self.is_valid,
            'total_items': self.total_items,
            'errors': [error.to_dict() for error in self.errors],
            'warnings': [warning.to_dict() for warning in self.warnings],
            'specification_compliance': self.specification_compliance,
            'performance_metrics': self.performance_metrics,
            'recommendations': self.recommendations
        }


@dataclass
class SocialPackageValidationReport:
    """Social package validation report with platform-specific details"""
    package_id: str
    platform: str
    is_valid: bool
    status: PackageStatus
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    compliance_issues: List[str] = field(default_factory=list)
    media_validation_results: Dict[str, ValidationResult] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'package_id': self.package_id,
            'platform': self.platform,
            'is_valid': self.is_valid,
            'status': self.status.value,
            'errors': [error.to_dict() for error in self.errors],
            'warnings': [warning.to_dict() for warning in self.warnings],
            'compliance_issues': self.compliance_issues,
            'media_validation_results': {
                k: v.to_dict() for k, v in self.media_validation_results.items()
            },
            'recommendations': self.recommendations
        }


class RSSFeedValidator:
    """Validates RSS feeds against RSS 2.0 specification"""
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize RSS feed validator
        
        Args:
            strict_mode: Enable strict validation (zero tolerance for errors)
        """
        self.strict_mode = strict_mode
        
        # RSS 2.0 specification requirements
        self.required_channel_elements = {'title', 'description', 'link'}
        self.optional_channel_elements = {
            'language', 'copyright', 'managingEditor', 'webMaster', 'pubDate',
            'lastBuildDate', 'category', 'generator', 'docs', 'cloud', 'ttl',
            'image', 'rating', 'textInput', 'skipHours', 'skipDays'
        }
        
        self.required_item_elements = set()  # RSS items have no strictly required elements
        self.recommended_item_elements = {'title', 'description', 'link', 'guid', 'pubDate'}
    
    def validate_rss_feed(self, rss_feed: RSSFeed) -> FeedValidationReport:
        """
        Validate RSS feed against RSS 2.0 specification
        
        Args:
            rss_feed: RSSFeed object to validate
            
        Returns:
            FeedValidationReport with validation results
        """
        errors = []
        warnings = []
        compliance = {}
        performance_metrics = {}
        recommendations = []
        
        # Validate channel elements
        channel_result = self._validate_channel_elements(rss_feed)
        errors.extend(channel_result.errors)
        warnings.extend(channel_result.warnings)
        compliance['channel_elements'] = len(channel_result.errors) == 0
        
        # Validate RSS items
        items_result = self._validate_rss_items(rss_feed.items)
        errors.extend(items_result.errors)
        warnings.extend(items_result.warnings)
        compliance['items_valid'] = len(items_result.errors) == 0
        
        # Validate XML structure
        xml_result = self._validate_xml_structure(rss_feed)
        errors.extend(xml_result.errors)
        warnings.extend(xml_result.warnings)
        compliance['xml_structure'] = len(xml_result.errors) == 0
        
        # Performance analysis
        performance_metrics = {
            'total_items': len(rss_feed.items),
            'average_title_length': self._calculate_average_title_length(rss_feed.items),
            'average_description_length': self._calculate_average_description_length(rss_feed.items),
            'items_with_enclosures': len([item for item in rss_feed.items if 'enclosure' in item]),
            'items_with_media': len([item for item in rss_feed.items if 'media_content' in item])
        }
        
        # Generate recommendations
        recommendations = self._generate_rss_recommendations(rss_feed, performance_metrics)
        
        # Overall validation status
        is_valid = len(errors) == 0 if self.strict_mode else len([e for e in errors if e.severity == Severity.ERROR]) == 0
        
        return FeedValidationReport(
            feed_type='rss',
            is_valid=is_valid,
            total_items=len(rss_feed.items),
            errors=errors,
            warnings=warnings,
            specification_compliance=compliance,
            performance_metrics=performance_metrics,
            recommendations=recommendations
        ) 
   
    def _validate_channel_elements(self, rss_feed: RSSFeed) -> ValidationResult:
        """Validate RSS channel elements"""
        errors = []
        warnings = []
        
        # Check required elements
        if not rss_feed.title:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="RSS channel title is required",
                location="channel.title",
                severity=Severity.ERROR
            ))
        
        if not rss_feed.description:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="RSS channel description is required",
                location="channel.description",
                severity=Severity.ERROR
            ))
        
        if not rss_feed.link:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="RSS channel link is required",
                location="channel.link",
                severity=Severity.ERROR
            ))
        
        # Validate link format
        if rss_feed.link and not self._is_valid_url(rss_feed.link):
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Invalid channel link URL: {rss_feed.link}",
                location="channel.link",
                severity=Severity.ERROR
            ))
        
        # Validate language format
        if rss_feed.language and not self._is_valid_language_code(rss_feed.language):
            warnings.append(ValidationWarning(
                message=f"Language code '{rss_feed.language}' may not be valid RFC 3066 format",
                location="channel.language"
            ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_rss_items(self, items: List[Dict[str, Any]]) -> ValidationResult:
        """Validate RSS items"""
        errors = []
        warnings = []
        
        for i, item in enumerate(items):
            # At least one of title or description should be present
            if not item.get('title') and not item.get('description'):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Item {i+1} must have either title or description",
                    location=f"item[{i}]",
                    severity=Severity.ERROR
                ))
            
            # Validate GUID uniqueness (simplified check)
            guid = item.get('guid')
            if guid:
                # Check if GUID looks like a valid identifier
                if not self._is_valid_guid(guid):
                    warnings.append(ValidationWarning(
                        message=f"Item {i+1} GUID may not be unique or properly formatted",
                        location=f"item[{i}].guid"
                    ))
            
            # Validate item link
            link = item.get('link')
            if link and not self._is_valid_url(link):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Item {i+1} has invalid link URL: {link}",
                    location=f"item[{i}].link",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_xml_structure(self, rss_feed: RSSFeed) -> ValidationResult:
        """Validate XML structure by generating and parsing"""
        errors = []
        warnings = []
        
        try:
            # Generate XML and try to parse it
            xml_content = rss_feed.to_xml()
            ET.fromstring(xml_content)
        except ET.ParseError as e:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Generated XML is not well-formed: {str(e)}",
                location="xml_structure",
                severity=Severity.ERROR
            ))
        except Exception as e:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"XML generation failed: {str(e)}",
                location="xml_generation",
                severity=Severity.ERROR
            ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _calculate_average_title_length(self, items: List[Dict[str, Any]]) -> float:
        """Calculate average title length for performance metrics"""
        titles = [item.get('title', '') for item in items if item.get('title')]
        return sum(len(title) for title in titles) / len(titles) if titles else 0.0
    
    def _calculate_average_description_length(self, items: List[Dict[str, Any]]) -> float:
        """Calculate average description length for performance metrics"""
        descriptions = [item.get('description', '') for item in items if item.get('description')]
        return sum(len(desc) for desc in descriptions) / len(descriptions) if descriptions else 0.0
    
    def _generate_rss_recommendations(self, rss_feed: RSSFeed, metrics: Dict[str, Any]) -> List[str]:
        """Generate recommendations for RSS feed improvement"""
        recommendations = []
        
        if metrics['total_items'] > 50:
            recommendations.append("Consider limiting RSS feed to 50 most recent items for better performance")
        
        if metrics['average_title_length'] > 100:
            recommendations.append("Consider shortening item titles for better readability")
        
        if metrics['items_with_enclosures'] == 0 and metrics['total_items'] > 0:
            recommendations.append("Consider adding media enclosures for richer content experience")
        
        if not rss_feed.language:
            recommendations.append("Add language element to channel for better feed compatibility")
        
        if not rss_feed.copyright:
            recommendations.append("Consider adding copyright information to protect content")
        
        return recommendations
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _is_valid_language_code(self, language: str) -> bool:
        """Validate language code format (simplified)"""
        # Basic check for RFC 3066 format (e.g., en-US, fr, de-DE)
        pattern = r'^[a-z]{2}(-[A-Z]{2})?$'
        return bool(re.match(pattern, language))
    
    def _is_valid_guid(self, guid: str) -> bool:
        """Validate GUID format (simplified)"""
        # Basic check - should be non-empty and reasonably unique looking
        return len(guid) > 10 and not guid.isspace()


# Factory functions

def create_feed_validators(strict_mode: bool = True) -> Dict[str, Union[RSSFeedValidator]]:
    """
    Create feed validators
    
    Args:
        strict_mode: Enable strict validation mode
        
    Returns:
        Dictionary of validator instances
    """
    return {
        'rss': RSSFeedValidator(strict_mode)
    }