"""
Schema Validator for JSON-LD and HTML validation

Implements JSON-LD validation against Structured Data Contract,
required field presence and format checking, and Schema.org compliance
validation with 100% success requirement.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union
from urllib.parse import urlparse
import html.parser

from .publishing_models import (
    ValidationResult, ValidationError, ValidationWarning, 
    ErrorType, Severity, Episode, Series, Host, Person
)


@dataclass
class StructuredDataContract:
    """Defines the structured data contract for JSON-LD validation"""
    
    # Required fields for all content types
    REQUIRED_CORE_FIELDS = {
        '@context', '@type', '@id', 'name', 'description', 
        'datePublished', 'publisher'
    }
    
    # Required fields for VideoObject/TVEpisode
    REQUIRED_VIDEO_FIELDS = {
        'uploadDate', 'duration', 'thumbnailUrl', 'contentUrl'
    }
    
    # Required fields for TVEpisode specifically
    REQUIRED_EPISODE_FIELDS = {
        'episodeNumber', 'partOfSeries'
    }
    
    # Required fields for Person objects
    REQUIRED_PERSON_FIELDS = {
        'name', 'url'
    }
    
    # Required fields for Organization (publisher)
    REQUIRED_ORGANIZATION_FIELDS = {
        'name', 'logo'
    }
    
    # Valid Schema.org types
    VALID_SCHEMA_TYPES = {
        'VideoObject', 'TVEpisode', 'TVSeries', 'Person', 
        'Organization', 'WebPage', 'BreadcrumbList'
    }
    
    # Valid contexts
    VALID_CONTEXTS = {
        'https://schema.org',
        'https://schema.org/',
        'http://schema.org',
        'http://schema.org/'
    }
    
    def get_required_fields(self, schema_type: str) -> Set[str]:
        """Get required fields for a specific schema type"""
        required = self.REQUIRED_CORE_FIELDS.copy()
        
        if schema_type in ['VideoObject', 'TVEpisode']:
            required.update(self.REQUIRED_VIDEO_FIELDS)
        
        if schema_type == 'TVEpisode':
            required.update(self.REQUIRED_EPISODE_FIELDS)
        
        if schema_type == 'Person':
            required.update(self.REQUIRED_PERSON_FIELDS)
        
        if schema_type == 'Organization':
            required.update(self.REQUIRED_ORGANIZATION_FIELDS)
        
        return required


class HTMLValidator(html.parser.HTMLParser):
    """HTML parser for validation"""
    
    def __init__(self):
        super().__init__()
        self.errors = []
        self.warnings = []
        self.json_ld_scripts = []
        self.links = []
        self.meta_tags = []
        self.tag_stack = []
        
    def handle_starttag(self, tag, attrs):
        """Handle opening HTML tags"""
        self.tag_stack.append(tag)
        attrs_dict = dict(attrs)
        
        # Collect JSON-LD scripts
        if tag == 'script' and attrs_dict.get('type') == 'application/ld+json':
            self.current_json_ld = True
        
        # Collect links
        if tag == 'a' and 'href' in attrs_dict:
            self.links.append(attrs_dict['href'])
        
        # Collect meta tags
        if tag == 'meta':
            self.meta_tags.append(attrs_dict)
    
    def handle_endtag(self, tag):
        """Handle closing HTML tags"""
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
        else:
            self.errors.append(f"Mismatched closing tag: {tag}")
    
    def handle_data(self, data):
        """Handle text data"""
        if hasattr(self, 'current_json_ld') and self.current_json_ld:
            try:
                json_data = json.loads(data.strip())
                self.json_ld_scripts.append(json_data)
            except json.JSONDecodeError as e:
                self.errors.append(f"Invalid JSON-LD: {e}")
            self.current_json_ld = False
    
    def error(self, message):
        """Handle parser errors"""
        self.errors.append(f"HTML parse error: {message}")


class SchemaValidator:
    """Validates JSON-LD structured data against Schema.org and contract requirements"""
    
    def __init__(self, contract: Optional[StructuredDataContract] = None):
        """
        Initialize schema validator
        
        Args:
            contract: Structured data contract (uses default if None)
        """
        self.contract = contract or StructuredDataContract()
    
    def validate_html_page(self, html_content: str, page_url: str) -> ValidationResult:
        """
        Validate complete HTML page including structure and embedded JSON-LD
        
        Args:
            html_content: HTML content to validate
            page_url: URL of the page being validated
            
        Returns:
            ValidationResult with comprehensive validation details
        """
        errors = []
        warnings = []
        
        # Parse HTML
        parser = HTMLValidator()
        try:
            parser.feed(html_content)
        except Exception as e:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"HTML parsing failed: {e}",
                location=page_url,
                severity=Severity.ERROR
            ))
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Check for HTML structure errors
        for error_msg in parser.errors:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=error_msg,
                location=page_url,
                severity=Severity.ERROR
            ))
        
        # Validate JSON-LD scripts
        if not parser.json_ld_scripts:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="No JSON-LD structured data found",
                location=page_url,
                severity=Severity.ERROR
            ))
        else:
            for i, json_ld in enumerate(parser.json_ld_scripts):
                json_ld_result = self.validate_json_ld(json_ld, f"{page_url}#json-ld-{i}")
                errors.extend(json_ld_result.errors)
                warnings.extend(json_ld_result.warnings)
        
        # Validate meta tags
        meta_result = self._validate_meta_tags(parser.meta_tags, page_url)
        errors.extend(meta_result.errors)
        warnings.extend(meta_result.warnings)
        
        # Check for canonical URL
        canonical_found = any(
            meta.get('rel') == 'canonical' for meta in parser.meta_tags
        )
        if not canonical_found:
            warnings.append(ValidationWarning(
                message="No canonical URL found",
                location=page_url
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'page_url': page_url,
                'json_ld_count': len(parser.json_ld_scripts),
                'links_count': len(parser.links),
                'meta_tags_count': len(parser.meta_tags)
            }
        )
    
    def validate_json_ld(self, json_ld_data: Dict[str, Any], location: str) -> ValidationResult:
        """
        Validate JSON-LD structured data against Schema.org compliance
        
        Args:
            json_ld_data: JSON-LD data to validate
            location: Location identifier for error reporting
            
        Returns:
            ValidationResult with validation details
        """
        errors = []
        warnings = []
        
        # Validate basic structure
        structure_result = self._validate_basic_structure(json_ld_data, location)
        errors.extend(structure_result.errors)
        warnings.extend(structure_result.warnings)
        
        if structure_result.errors:
            # If basic structure is invalid, don't continue
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Get schema type
        schema_type = json_ld_data.get('@type')
        if isinstance(schema_type, list):
            schema_type = schema_type[0]  # Use first type if multiple
        
        # Validate required fields
        required_fields_result = self._validate_required_fields(json_ld_data, schema_type, location)
        errors.extend(required_fields_result.errors)
        warnings.extend(required_fields_result.warnings)
        
        # Validate field formats
        format_result = self._validate_field_formats(json_ld_data, location)
        errors.extend(format_result.errors)
        warnings.extend(format_result.warnings)
        
        # Validate relationships
        relationships_result = self._validate_relationships(json_ld_data, location)
        errors.extend(relationships_result.errors)
        warnings.extend(relationships_result.warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'schema_type': schema_type, 'location': location}
        )
    
    def validate_episode_json_ld(self, episode: Episode, json_ld_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate JSON-LD data specifically for an episode
        
        Args:
            episode: Episode object to validate against
            json_ld_data: JSON-LD data to validate
            
        Returns:
            ValidationResult with episode-specific validation
        """
        errors = []
        warnings = []
        
        # First run standard JSON-LD validation
        standard_result = self.validate_json_ld(json_ld_data, f"episode:{episode.episode_id}")
        errors.extend(standard_result.errors)
        warnings.extend(standard_result.warnings)
        
        # Episode-specific validations
        if json_ld_data.get('name') != episode.title:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"JSON-LD name '{json_ld_data.get('name')}' doesn't match episode title '{episode.title}'",
                location=f"episode:{episode.episode_id}.name",
                severity=Severity.ERROR
            ))
        
        if json_ld_data.get('description') != episode.description:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="JSON-LD description doesn't match episode description",
                location=f"episode:{episode.episode_id}.description",
                severity=Severity.ERROR
            ))
        
        # Validate duration format
        json_duration = json_ld_data.get('duration')
        if json_duration:
            if not self._is_valid_iso8601_duration(json_duration):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Invalid ISO 8601 duration format: {json_duration}",
                    location=f"episode:{episode.episode_id}.duration",
                    severity=Severity.ERROR
                ))
        
        # Validate series reference
        part_of_series = json_ld_data.get('partOfSeries')
        if part_of_series:
            if isinstance(part_of_series, dict):
                if part_of_series.get('name') != episode.series.title:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message="Series name in JSON-LD doesn't match episode series",
                        location=f"episode:{episode.episode_id}.partOfSeries.name",
                        severity=Severity.ERROR
                    ))
        
        # Validate social links in sameAs
        same_as = json_ld_data.get('sameAs', [])
        if isinstance(same_as, str):
            same_as = [same_as]
        
        for platform, url in episode.social_links.items():
            if url not in same_as:
                warnings.append(ValidationWarning(
                    message=f"Social link for {platform} not found in sameAs array",
                    location=f"episode:{episode.episode_id}.sameAs"
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'episode_id': episode.episode_id}
        )
    
    def _validate_basic_structure(self, json_ld_data: Dict[str, Any], location: str) -> ValidationResult:
        """Validate basic JSON-LD structure"""
        errors = []
        warnings = []
        
        # Check @context
        context = json_ld_data.get('@context')
        if not context:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="Missing @context field",
                location=f"{location}.@context",
                severity=Severity.ERROR
            ))
        elif context not in self.contract.VALID_CONTEXTS:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Invalid @context: {context}",
                location=f"{location}.@context",
                severity=Severity.ERROR
            ))
        
        # Check @type
        schema_type = json_ld_data.get('@type')
        if not schema_type:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="Missing @type field",
                location=f"{location}.@type",
                severity=Severity.ERROR
            ))
        else:
            # Handle multiple types
            types_to_check = schema_type if isinstance(schema_type, list) else [schema_type]
            valid_types = [t for t in types_to_check if t in self.contract.VALID_SCHEMA_TYPES]
            
            if not valid_types:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Invalid @type: {schema_type}",
                    location=f"{location}.@type",
                    severity=Severity.ERROR
                ))
        
        # Check @id
        if not json_ld_data.get('@id'):
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message="Missing @id field",
                location=f"{location}.@id",
                severity=Severity.ERROR
            ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_required_fields(self, json_ld_data: Dict[str, Any], schema_type: str, location: str) -> ValidationResult:
        """Validate presence of required fields"""
        errors = []
        warnings = []
        
        if not schema_type or schema_type not in self.contract.VALID_SCHEMA_TYPES:
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
        
        required_fields = self.contract.get_required_fields(schema_type)
        
        for field in required_fields:
            if field not in json_ld_data:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Missing required field: {field}",
                    location=f"{location}.{field}",
                    severity=Severity.ERROR
                ))
            elif not json_ld_data[field]:  # Check for empty values
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Required field is empty: {field}",
                    location=f"{location}.{field}",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_field_formats(self, json_ld_data: Dict[str, Any], location: str) -> ValidationResult:
        """Validate field formats and values"""
        errors = []
        warnings = []
        
        # Validate date fields
        date_fields = ['datePublished', 'uploadDate', 'dateModified', 'dateCreated']
        for field in date_fields:
            if field in json_ld_data:
                if not self._is_valid_iso8601_date(json_ld_data[field]):
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Invalid ISO 8601 date format in {field}: {json_ld_data[field]}",
                        location=f"{location}.{field}",
                        severity=Severity.ERROR
                    ))
        
        # Validate duration
        if 'duration' in json_ld_data:
            if not self._is_valid_iso8601_duration(json_ld_data['duration']):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Invalid ISO 8601 duration format: {json_ld_data['duration']}",
                    location=f"{location}.duration",
                    severity=Severity.ERROR
                ))
        
        # Validate URLs
        url_fields = ['url', 'contentUrl', 'thumbnailUrl', 'sameAs']
        for field in url_fields:
            if field in json_ld_data:
                urls = json_ld_data[field]
                if isinstance(urls, str):
                    urls = [urls]
                elif not isinstance(urls, list):
                    continue
                
                for url in urls:
                    if not self._is_valid_url(url):
                        errors.append(ValidationError(
                            error_type=ErrorType.SCHEMA_VALIDATION,
                            message=f"Invalid URL in {field}: {url}",
                            location=f"{location}.{field}",
                            severity=Severity.ERROR
                        ))
        
        # Validate numeric fields
        if 'episodeNumber' in json_ld_data:
            try:
                episode_num = int(json_ld_data['episodeNumber'])
                if episode_num <= 0:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Episode number must be positive: {episode_num}",
                        location=f"{location}.episodeNumber",
                        severity=Severity.ERROR
                    ))
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Episode number must be numeric: {json_ld_data['episodeNumber']}",
                    location=f"{location}.episodeNumber",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_relationships(self, json_ld_data: Dict[str, Any], location: str) -> ValidationResult:
        """Validate object relationships and references"""
        errors = []
        warnings = []
        
        # Validate partOfSeries for episodes
        if json_ld_data.get('@type') == 'TVEpisode':
            part_of_series = json_ld_data.get('partOfSeries')
            if part_of_series:
                if isinstance(part_of_series, dict):
                    # Validate embedded series object
                    if not part_of_series.get('@type') == 'TVSeries':
                        errors.append(ValidationError(
                            error_type=ErrorType.SCHEMA_VALIDATION,
                            message="partOfSeries must be of type TVSeries",
                            location=f"{location}.partOfSeries.@type",
                            severity=Severity.ERROR
                        ))
                    
                    if not part_of_series.get('name'):
                        errors.append(ValidationError(
                            error_type=ErrorType.SCHEMA_VALIDATION,
                            message="partOfSeries must have a name",
                            location=f"{location}.partOfSeries.name",
                            severity=Severity.ERROR
                        ))
        
        # Validate actor/host references
        people_fields = ['actor', 'director', 'producer']
        for field in people_fields:
            if field in json_ld_data:
                people = json_ld_data[field]
                if not isinstance(people, list):
                    people = [people]
                
                for i, person in enumerate(people):
                    if isinstance(person, dict):
                        if not person.get('@type') == 'Person':
                            errors.append(ValidationError(
                                error_type=ErrorType.SCHEMA_VALIDATION,
                                message=f"{field} must be of type Person",
                                location=f"{location}.{field}[{i}].@type",
                                severity=Severity.ERROR
                            ))
                        
                        if not person.get('name'):
                            errors.append(ValidationError(
                                error_type=ErrorType.SCHEMA_VALIDATION,
                                message=f"{field} must have a name",
                                location=f"{location}.{field}[{i}].name",
                                severity=Severity.ERROR
                            ))
        
        # Validate publisher
        publisher = json_ld_data.get('publisher')
        if publisher and isinstance(publisher, dict):
            if not publisher.get('@type') == 'Organization':
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message="Publisher must be of type Organization",
                    location=f"{location}.publisher.@type",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _validate_meta_tags(self, meta_tags: List[Dict[str, str]], page_url: str) -> ValidationResult:
        """Validate HTML meta tags"""
        errors = []
        warnings = []
        
        # Check for essential meta tags
        meta_names = {meta.get('name', '').lower() for meta in meta_tags}
        meta_properties = {meta.get('property', '').lower() for meta in meta_tags}
        
        # Check for description
        if 'description' not in meta_names:
            warnings.append(ValidationWarning(
                message="Missing meta description tag",
                location=page_url
            ))
        
        # Check for Open Graph tags
        required_og_tags = {'og:title', 'og:description', 'og:type', 'og:url'}
        missing_og_tags = required_og_tags - meta_properties
        
        if missing_og_tags:
            warnings.append(ValidationWarning(
                message=f"Missing Open Graph tags: {', '.join(missing_og_tags)}",
                location=page_url
            ))
        
        # Check for Twitter Card tags
        if 'twitter:card' not in meta_names:
            warnings.append(ValidationWarning(
                message="Missing Twitter Card meta tag",
                location=page_url
            ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _is_valid_iso8601_date(self, date_str: str) -> bool:
        """Check if string is valid ISO 8601 date"""
        try:
            datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return True
        except (ValueError, AttributeError):
            return False
    
    def _is_valid_iso8601_duration(self, duration_str: str) -> bool:
        """Check if string is valid ISO 8601 duration"""
        # Pattern for ISO 8601 duration: PT[n]H[n]M[n]S
        pattern = r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$'
        return bool(re.match(pattern, duration_str))
    
    def _is_valid_url(self, url_str: str) -> bool:
        """Check if string is valid URL"""
        try:
            result = urlparse(url_str)
            return all([result.scheme, result.netloc])
        except Exception:
            return False


def create_schema_validator(contract: Optional[StructuredDataContract] = None) -> SchemaValidator:
    """
    Factory function to create schema validator
    
    Args:
        contract: Structured data contract (uses default if None)
        
    Returns:
        SchemaValidator instance
    """
    return SchemaValidator(contract)