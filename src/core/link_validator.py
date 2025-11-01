"""
Link Validator for internal link integrity checking

Implements internal link integrity checker with zero broken link tolerance,
canonical URL validation and redirect chain checking, and cross-reference
validation between content types.
"""

import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin, urlparse, urlunparse
import html.parser

from .publishing_models import (
    ValidationResult, ValidationError, ValidationWarning,
    ErrorType, Severity, Episode, Series, Host, Person
)


@dataclass
class BrokenLink:
    """Details of a broken link"""
    source_url: str
    target_url: str
    link_text: str
    error_type: str
    error_message: str
    line_number: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_url': self.source_url,
            'target_url': self.target_url,
            'link_text': self.link_text,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'line_number': self.line_number
        }


@dataclass
class RedirectChain:
    """Details of a redirect chain"""
    original_url: str
    final_url: str
    redirects: List[Tuple[str, int]]  # (url, status_code)
    chain_length: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'original_url': self.original_url,
            'final_url': self.final_url,
            'redirects': [{'url': url, 'status_code': code} for url, code in self.redirects],
            'chain_length': self.chain_length
        }


@dataclass
class CanonicalURLIssue:
    """Issues with canonical URLs"""
    page_url: str
    canonical_url: Optional[str]
    issue_type: str
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'page_url': self.page_url,
            'canonical_url': self.canonical_url,
            'issue_type': self.issue_type,
            'message': self.message
        }


class LinkExtractor(html.parser.HTMLParser):
    """HTML parser to extract links and references"""
    
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links = []
        self.canonical_url = None
        self.meta_tags = []
        self.images = []
        self.scripts = []
        self.stylesheets = []
        self.current_line = 1
        
    def handle_starttag(self, tag, attrs):
        """Handle opening HTML tags"""
        attrs_dict = dict(attrs)
        
        # Extract links
        if tag == 'a' and 'href' in attrs_dict:
            href = attrs_dict['href']
            text = attrs_dict.get('title', '')
            self.links.append({
                'url': self._resolve_url(href),
                'original_href': href,
                'text': text,
                'line': self.current_line,
                'tag': tag
            })
        
        # Extract canonical URL
        elif tag == 'link' and attrs_dict.get('rel') == 'canonical':
            self.canonical_url = self._resolve_url(attrs_dict.get('href', ''))
        
        # Extract other link elements
        elif tag == 'link':
            if 'href' in attrs_dict:
                self.stylesheets.append({
                    'url': self._resolve_url(attrs_dict['href']),
                    'rel': attrs_dict.get('rel', ''),
                    'line': self.current_line
                })
        
        # Extract images
        elif tag == 'img' and 'src' in attrs_dict:
            self.images.append({
                'url': self._resolve_url(attrs_dict['src']),
                'alt': attrs_dict.get('alt', ''),
                'line': self.current_line
            })
        
        # Extract scripts
        elif tag == 'script' and 'src' in attrs_dict:
            self.scripts.append({
                'url': self._resolve_url(attrs_dict['src']),
                'line': self.current_line
            })
        
        # Extract meta tags
        elif tag == 'meta':
            self.meta_tags.append(attrs_dict)
    
    def handle_data(self, data):
        """Handle text data"""
        self.current_line += data.count('\n')
    
    def _resolve_url(self, url: str) -> str:
        """Resolve relative URLs to absolute URLs"""
        if not url:
            return url
        return urljoin(self.base_url, url)


class LinkValidator:
    """Validates internal link integrity with zero broken link tolerance"""
    
    def __init__(self, 
                 base_domain: str,
                 content_registry: Optional[Dict[str, Any]] = None,
                 max_redirect_chain: int = 5):
        """
        Initialize link validator
        
        Args:
            base_domain: Base domain for internal link validation
            content_registry: Registry of available content for cross-reference validation
            max_redirect_chain: Maximum allowed redirect chain length
        """
        self.base_domain = base_domain.rstrip('/')
        self.content_registry = content_registry or {}
        self.max_redirect_chain = max_redirect_chain
        self.url_patterns = self._build_url_patterns()
    
    def validate_page_links(self, 
                           html_content: str, 
                           page_url: str,
                           available_pages: Optional[Set[str]] = None) -> ValidationResult:
        """
        Validate all links in an HTML page
        
        Args:
            html_content: HTML content to validate
            page_url: URL of the page being validated
            available_pages: Set of available page URLs for validation
            
        Returns:
            ValidationResult with link validation details
        """
        errors = []
        warnings = []
        broken_links = []
        
        # Extract links from HTML
        extractor = LinkExtractor(page_url)
        try:
            extractor.feed(html_content)
        except Exception as e:
            errors.append(ValidationError(
                error_type=ErrorType.LINK_VALIDATION,
                message=f"Failed to parse HTML for link extraction: {e}",
                location=page_url,
                severity=Severity.ERROR
            ))
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Validate internal links
        internal_links = [link for link in extractor.links if self._is_internal_link(link['url'])]
        
        for link in internal_links:
            link_result = self._validate_internal_link(
                link, page_url, available_pages or set()
            )
            
            if not link_result.is_valid:
                broken_links.extend([
                    BrokenLink(
                        source_url=page_url,
                        target_url=link['url'],
                        link_text=link['text'],
                        error_type=error.error_type.value,
                        error_message=error.message,
                        line_number=link.get('line')
                    ) for error in link_result.errors
                ])
                errors.extend(link_result.errors)
            
            warnings.extend(link_result.warnings)
        
        # Validate images
        for image in extractor.images:
            if self._is_internal_link(image['url']):
                if not self._url_exists(image['url'], available_pages or set()):
                    broken_links.append(BrokenLink(
                        source_url=page_url,
                        target_url=image['url'],
                        link_text=image['alt'],
                        error_type='missing_image',
                        error_message=f"Image not found: {image['url']}",
                        line_number=image.get('line')
                    ))
                    errors.append(ValidationError(
                        error_type=ErrorType.LINK_VALIDATION,
                        message=f"Missing image: {image['url']}",
                        location=f"{page_url}:line-{image.get('line', 'unknown')}",
                        severity=Severity.ERROR
                    ))
        
        # Validate stylesheets and scripts
        for resource in extractor.stylesheets + extractor.scripts:
            if self._is_internal_link(resource['url']):
                if not self._url_exists(resource['url'], available_pages or set()):
                    resource_type = 'stylesheet' if resource in extractor.stylesheets else 'script'
                    errors.append(ValidationError(
                        error_type=ErrorType.LINK_VALIDATION,
                        message=f"Missing {resource_type}: {resource['url']}",
                        location=f"{page_url}:line-{resource.get('line', 'unknown')}",
                        severity=Severity.ERROR
                    ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'page_url': page_url,
                'internal_links_count': len(internal_links),
                'broken_links': [link.to_dict() for link in broken_links],
                'images_count': len(extractor.images),
                'resources_count': len(extractor.stylesheets) + len(extractor.scripts)
            }
        )
    
    def validate_canonical_urls(self, pages: List[Dict[str, str]]) -> ValidationResult:
        """
        Validate canonical URL configuration across pages
        
        Args:
            pages: List of page dictionaries with 'url' and 'html_content' keys
            
        Returns:
            ValidationResult with canonical URL validation details
        """
        errors = []
        warnings = []
        canonical_issues = []
        
        canonical_map = {}  # canonical_url -> [page_urls]
        
        for page in pages:
            page_url = page['url']
            html_content = page['html_content']
            
            # Extract canonical URL
            extractor = LinkExtractor(page_url)
            try:
                extractor.feed(html_content)
            except Exception as e:
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message=f"Failed to parse HTML for canonical URL: {e}",
                    location=page_url,
                    severity=Severity.ERROR
                ))
                continue
            
            canonical_url = extractor.canonical_url
            
            # Check for missing canonical URL
            if not canonical_url:
                canonical_issues.append(CanonicalURLIssue(
                    page_url=page_url,
                    canonical_url=None,
                    issue_type='missing_canonical',
                    message="No canonical URL specified"
                ))
                warnings.append(ValidationWarning(
                    message="Missing canonical URL",
                    location=page_url
                ))
                continue
            
            # Check canonical URL format
            if not self._is_valid_canonical_url(canonical_url, page_url):
                canonical_issues.append(CanonicalURLIssue(
                    page_url=page_url,
                    canonical_url=canonical_url,
                    issue_type='invalid_canonical',
                    message=f"Invalid canonical URL: {canonical_url}"
                ))
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message=f"Invalid canonical URL: {canonical_url}",
                    location=page_url,
                    severity=Severity.ERROR
                ))
                continue
            
            # Track canonical mappings
            if canonical_url not in canonical_map:
                canonical_map[canonical_url] = []
            canonical_map[canonical_url].append(page_url)
        
        # Check for duplicate canonical URLs
        for canonical_url, page_urls in canonical_map.items():
            if len(page_urls) > 1:
                canonical_issues.append(CanonicalURLIssue(
                    page_url=', '.join(page_urls),
                    canonical_url=canonical_url,
                    issue_type='duplicate_canonical',
                    message=f"Multiple pages with same canonical URL: {canonical_url}"
                ))
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message=f"Duplicate canonical URL {canonical_url} used by: {', '.join(page_urls)}",
                    location="canonical_urls",
                    severity=Severity.ERROR
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'canonical_issues': [issue.to_dict() for issue in canonical_issues],
                'pages_with_canonical': len([p for p in pages if canonical_map]),
                'total_pages': len(pages)
            }
        )
    
    def validate_cross_references(self, 
                                episodes: List[Episode],
                                series: List[Series],
                                hosts: List[Host]) -> ValidationResult:
        """
        Validate cross-reference integrity between content types
        
        Args:
            episodes: List of episodes to validate
            series: List of series to validate
            hosts: List of hosts to validate
            
        Returns:
            ValidationResult with cross-reference validation details
        """
        errors = []
        warnings = []
        
        # Build lookup maps
        series_map = {s.series_id: s for s in series}
        host_map = {h.host_id: h for h in hosts}
        
        # Validate episode references
        for episode in episodes:
            # Check series reference
            if episode.series.series_id not in series_map:
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message=f"Episode references non-existent series: {episode.series.series_id}",
                    location=f"episode:{episode.episode_id}.series_id",
                    severity=Severity.ERROR
                ))
            
            # Check host references
            for host in episode.hosts:
                if host.host_id not in host_map:
                    errors.append(ValidationError(
                        error_type=ErrorType.LINK_VALIDATION,
                        message=f"Episode references non-existent host: {host.host_id}",
                        location=f"episode:{episode.episode_id}.hosts",
                        severity=Severity.ERROR
                    ))
        
        # Validate series references
        for series in series:
            # Check primary host reference
            if series.primary_host.host_id not in host_map:
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message=f"Series references non-existent primary host: {series.primary_host.host_id}",
                    location=f"series:{series.series_id}.primary_host",
                    severity=Severity.ERROR
                ))
        
        # Validate host references
        for host in hosts:
            # Check show references
            for show_id in host.shows:
                if show_id not in series_map:
                    warnings.append(ValidationWarning(
                        message=f"Host references non-existent show: {show_id}",
                        location=f"host:{host.host_id}.shows"
                    ))
        
        # Check for orphaned content
        referenced_series = {ep.series.series_id for ep in episodes}
        orphaned_series = [s.series_id for s in series if s.series_id not in referenced_series]
        
        if orphaned_series:
            warnings.append(ValidationWarning(
                message=f"Orphaned series (no episodes): {', '.join(orphaned_series)}",
                location="series_registry"
            ))
        
        referenced_hosts = set()
        for episode in episodes:
            referenced_hosts.update(h.host_id for h in episode.hosts)
        for series in series:
            referenced_hosts.add(series.primary_host.host_id)
        
        orphaned_hosts = [h.host_id for h in hosts if h.host_id not in referenced_hosts]
        
        if orphaned_hosts:
            warnings.append(ValidationWarning(
                message=f"Orphaned hosts (not referenced): {', '.join(orphaned_hosts)}",
                location="host_registry"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'episodes_count': len(episodes),
                'series_count': len(series),
                'hosts_count': len(hosts),
                'orphaned_series': orphaned_series,
                'orphaned_hosts': orphaned_hosts
            }
        )
    
    def check_redirect_chains(self, redirects: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate redirect chains for proper configuration
        
        Args:
            redirects: List of redirect configurations
            
        Returns:
            ValidationResult with redirect chain validation
        """
        errors = []
        warnings = []
        redirect_chains = []
        
        # Build redirect map
        redirect_map = {}
        for redirect in redirects:
            source = redirect.get('source_url', '').rstrip('/')
            target = redirect.get('target_url', '').rstrip('/')
            status_code = redirect.get('status_code', 301)
            
            if not source or not target:
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message="Redirect missing source or target URL",
                    location=f"redirect:{source or 'unknown'}",
                    severity=Severity.ERROR
                ))
                continue
            
            redirect_map[source] = (target, status_code)
        
        # Check for redirect chains and loops
        for source_url in redirect_map:
            chain = self._trace_redirect_chain(source_url, redirect_map)
            
            if chain.chain_length > self.max_redirect_chain:
                redirect_chains.append(chain)
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message=f"Redirect chain too long ({chain.chain_length} > {self.max_redirect_chain}): {source_url}",
                    location=f"redirect:{source_url}",
                    severity=Severity.ERROR
                ))
            
            # Check for redirect loops
            urls_in_chain = {url for url, _ in chain.redirects}
            if len(urls_in_chain) != len(chain.redirects):
                errors.append(ValidationError(
                    error_type=ErrorType.LINK_VALIDATION,
                    message=f"Redirect loop detected starting from: {source_url}",
                    location=f"redirect:{source_url}",
                    severity=Severity.ERROR
                ))
            
            # Check for non-301 redirects in chains
            non_permanent_redirects = [
                (url, code) for url, code in chain.redirects if code != 301
            ]
            if non_permanent_redirects and chain.chain_length > 1:
                warnings.append(ValidationWarning(
                    message=f"Non-permanent redirects in chain: {source_url}",
                    location=f"redirect:{source_url}"
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'redirect_chains': [chain.to_dict() for chain in redirect_chains],
                'total_redirects': len(redirects),
                'max_chain_length': max((chain.chain_length for chain in redirect_chains), default=0)
            }
        )
    
    def _validate_internal_link(self, 
                               link: Dict[str, Any], 
                               source_url: str,
                               available_pages: Set[str]) -> ValidationResult:
        """Validate a single internal link"""
        errors = []
        warnings = []
        
        target_url = link['url']
        
        # Check if URL exists
        if not self._url_exists(target_url, available_pages):
            errors.append(ValidationError(
                error_type=ErrorType.LINK_VALIDATION,
                message=f"Broken internal link: {target_url}",
                location=f"{source_url}:line-{link.get('line', 'unknown')}",
                severity=Severity.ERROR
            ))
        
        # Check URL format
        if not self._is_valid_url_format(target_url):
            errors.append(ValidationError(
                error_type=ErrorType.LINK_VALIDATION,
                message=f"Invalid URL format: {target_url}",
                location=f"{source_url}:line-{link.get('line', 'unknown')}",
                severity=Severity.ERROR
            ))
        
        # Check for fragment-only links
        parsed = urlparse(target_url)
        if parsed.fragment and not parsed.path and not parsed.netloc:
            # This is a fragment-only link (#section), validate it exists on current page
            warnings.append(ValidationWarning(
                message=f"Fragment-only link (ensure target exists): {target_url}",
                location=f"{source_url}:line-{link.get('line', 'unknown')}"
            ))
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _is_internal_link(self, url: str) -> bool:
        """Check if URL is an internal link"""
        if not url:
            return False
        
        parsed = urlparse(url)
        
        # Relative URLs are internal
        if not parsed.netloc:
            return True
        
        # Check if domain matches
        return parsed.netloc == urlparse(self.base_domain).netloc
    
    def _url_exists(self, url: str, available_pages: Set[str]) -> bool:
        """Check if URL exists in available pages"""
        # Normalize URL for comparison
        normalized_url = self._normalize_url(url)
        normalized_pages = {self._normalize_url(page) for page in available_pages}
        
        return normalized_url in normalized_pages
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        parsed = urlparse(url)
        
        # Remove fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/') or '/',
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        
        return normalized.lower()
    
    def _is_valid_url_format(self, url: str) -> bool:
        """Check if URL has valid format"""
        try:
            parsed = urlparse(url)
            return True
        except Exception:
            return False
    
    def _is_valid_canonical_url(self, canonical_url: str, page_url: str) -> bool:
        """Check if canonical URL is valid"""
        if not canonical_url:
            return False
        
        # Must be absolute URL
        parsed = urlparse(canonical_url)
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Should be on same domain (for internal content)
        page_domain = urlparse(page_url).netloc
        canonical_domain = parsed.netloc
        
        return canonical_domain == page_domain
    
    def _trace_redirect_chain(self, 
                             start_url: str, 
                             redirect_map: Dict[str, Tuple[str, int]]) -> RedirectChain:
        """Trace a redirect chain to its end"""
        chain = []
        current_url = start_url
        visited = set()
        
        while current_url in redirect_map and current_url not in visited:
            visited.add(current_url)
            target_url, status_code = redirect_map[current_url]
            chain.append((current_url, status_code))
            current_url = target_url
        
        final_url = current_url
        
        return RedirectChain(
            original_url=start_url,
            final_url=final_url,
            redirects=chain,
            chain_length=len(chain)
        )
    
    def _build_url_patterns(self) -> Dict[str, str]:
        """Build URL patterns for content types"""
        return {
            'episode': r'/episodes/([^/]+)/?$',
            'series': r'/series/([^/]+)/?$',
            'host': r'/hosts/([^/]+)/?$',
            'feed': r'/feeds/([^/]+\.xml)$',
            'sitemap': r'/sitemap([^/]*\.xml)$'
        }


def create_link_validator(base_domain: str, 
                         content_registry: Optional[Dict[str, Any]] = None,
                         max_redirect_chain: int = 5) -> LinkValidator:
    """
    Factory function to create link validator
    
    Args:
        base_domain: Base domain for internal link validation
        content_registry: Registry of available content
        max_redirect_chain: Maximum allowed redirect chain length
        
    Returns:
        LinkValidator instance
    """
    return LinkValidator(base_domain, content_registry, max_redirect_chain)