"""
Deployment Pipeline for Content Publishing Platform

Implements staging deployment, validation gates, production promotion,
and rollback capabilities with configurable thresholds and batch processing.
"""

import json
import shutil
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

from .publishing_models import (
    PublishManifest, Episode, Series, Host, ValidationResult, ValidationError, 
    ValidationWarning, ErrorType, Severity
)
from .content_registry import ContentRegistry
from .web_generator import WebGenerator, HTMLPage
from .feed_generator import FeedGenerator
from .social_generator import SocialGenerator
from .schema_validator import SchemaValidator
from .link_validator import LinkValidator
from .feed_validator import RSSFeedValidator
from .compliance_validator import ComplianceValidator

# Optional import to avoid circular dependency
try:
    from .analytics_tracker import AnalyticsTracker
except ImportError:
    AnalyticsTracker = None


class DeploymentStatus(Enum):
    """Deployment status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Environment(Enum):
    """Deployment environment enumeration"""
    STAGING = "staging"
    PRODUCTION = "production"


class ValidationGateType(Enum):
    """Types of validation gates"""
    HTML_STRUCTURE = "html_structure"
    SCHEMA_COMPLIANCE = "schema_compliance"
    LINK_INTEGRITY = "link_integrity"
    FEED_VALIDATION = "feed_validation"
    SOCIAL_PACKAGE = "social_package"


@dataclass
class DeploymentConfig:
    """Configuration for deployment pipeline"""
    # Batch processing settings
    batch_size: int = 50
    max_concurrent_workers: int = 4
    timeout_seconds: int = 300
    
    # Validation gate thresholds
    html_parse_failure_threshold: int = 0  # Zero tolerance
    broken_link_threshold: int = 0  # Zero tolerance
    schema_compliance_threshold: float = 1.0  # 100% success rate
    feed_validation_threshold: float = 1.0  # 100% success rate
    social_package_failure_threshold: float = 0.1  # 10% failure allowed
    
    # Environment paths
    staging_root: str = "data/staging"
    production_root: str = "data/public"
    backup_root: str = "data/backups"
    
    # Rollback settings
    max_rollback_history: int = 10
    rollback_timeout_seconds: int = 60
    
    # Social package settings
    social_validation_enabled: bool = True
    social_strict_mode: bool = False  # If True, social failures block web deployment


@dataclass
class ContentCounts:
    """Content counts for deployment reporting"""
    episodes: int = 0
    series: int = 0
    hosts: int = 0
    pages_generated: int = 0
    feeds_generated: int = 0
    social_packages: int = 0
    social_packages_valid: int = 0


@dataclass
class ValidationGateResult:
    """Result from a validation gate"""
    gate_type: ValidationGateType
    passed: bool
    threshold: float
    actual_score: float
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Comprehensive validation report"""
    overall_passed: bool
    gate_results: List[ValidationGateResult] = field(default_factory=list)
    total_errors: int = 0
    total_warnings: int = 0
    validation_timestamp: datetime = field(default_factory=datetime.now)
    
    def get_gate_result(self, gate_type: ValidationGateType) -> Optional[ValidationGateResult]:
        """Get result for specific validation gate"""
        for result in self.gate_results:
            if result.gate_type == gate_type:
                return result
        return None


@dataclass
class DeploymentResult:
    """Result from a deployment operation"""
    deployment_id: str
    status: DeploymentStatus
    environment: Environment
    content_counts: ContentCounts
    validation_report: Optional[ValidationReport] = None
    deployed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_available: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentHistory:
    """Deployment history entry"""
    deployment_id: str
    environment: Environment
    status: DeploymentStatus
    deployed_at: datetime
    manifest_build_id: str
    content_counts: ContentCounts
    rollback_from: Optional[str] = None  # If this was a rollback, original deployment ID


class StagingDeployment:
    """
    Staging deployment system with content validation and batch processing
    
    Handles deployment to staging environment with configurable concurrency limits,
    progress reporting, and comprehensive validation.
    """
    
    def __init__(self, config: DeploymentConfig):
        """
        Initialize staging deployment system
        
        Args:
            config: Deployment configuration
        """
        self.config = config
        self.staging_path = Path(config.staging_root)
        
        # Initialize components
        self.content_registry = ContentRegistry()
        self.web_generator = WebGenerator()
        self.feed_generator = FeedGenerator()
        self.social_generator = SocialGenerator()
        
        # Initialize validators
        self.schema_validator = SchemaValidator()
        self.link_validator = LinkValidator()
        self.rss_validator = RSSFeedValidator()
        self.sitemap_validator = XMLSitemapValidator()
        self.compliance_validator = ComplianceValidator()
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[str, float], None]] = None
        
    def set_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """Set callback for progress reporting"""
        self.progress_callback = callback
    
    def _report_progress(self, message: str, progress: float) -> None:
        """Report progress if callback is set"""
        if self.progress_callback:
            self.progress_callback(message, progress)
    
    def deploy_to_staging(self, manifest_path: str) -> DeploymentResult:
        """
        Deploy content to staging environment with validation
        
        Args:
            manifest_path: Path to publish manifest
            
        Returns:
            DeploymentResult with deployment status and details
        """
        deployment_id = f"staging_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            self._report_progress("Loading manifest", 0.0)
            
            # Load and validate manifest
            manifest = self.content_registry.load_manifest(manifest_path)
            
            # Prepare staging environment
            self._prepare_staging_environment(deployment_id)
            
            self._report_progress("Generating content", 0.1)
            
            # Generate content in batches
            content_counts = self._generate_content_batches(manifest, deployment_id)
            
            self._report_progress("Content generation complete", 0.8)
            
            # Create deployment result
            result = DeploymentResult(
                deployment_id=deployment_id,
                status=DeploymentStatus.COMPLETED,
                environment=Environment.STAGING,
                content_counts=content_counts,
                deployed_at=datetime.now(),
                completed_at=datetime.now(),
                rollback_available=False,  # Staging doesn't need rollback
                metadata={
                    "manifest_build_id": manifest.build_id,
                    "manifest_version": manifest.manifest_version,
                    "staging_path": str(self.staging_path / deployment_id)
                }
            )
            
            self._report_progress("Staging deployment complete", 1.0)
            return result
            
        except Exception as e:
            error_result = DeploymentResult(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                environment=Environment.STAGING,
                content_counts=ContentCounts(),
                error_message=str(e),
                metadata={"error_type": type(e).__name__}
            )
            
            self._report_progress(f"Staging deployment failed: {str(e)}", 1.0)
            return error_result
    
    def _prepare_staging_environment(self, deployment_id: str) -> None:
        """Prepare staging environment directory structure"""
        deployment_path = self.staging_path / deployment_id
        
        # Create directory structure
        directories = [
            deployment_path,
            deployment_path / "episodes",
            deployment_path / "series", 
            deployment_path / "hosts",
            deployment_path / "feeds",
            deployment_path / "assets",
            deployment_path / "social"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _generate_content_batches(self, manifest: PublishManifest, deployment_id: str) -> ContentCounts:
        """
        Generate content in configurable batches with concurrency control
        
        Args:
            manifest: Publishing manifest
            deployment_id: Deployment identifier
            
        Returns:
            ContentCounts with generation statistics
        """
        deployment_path = self.staging_path / deployment_id
        counts = ContentCounts()
        
        # Get all episodes
        episodes = self.content_registry.get_episodes()
        total_episodes = len(episodes)
        
        # Process episodes in batches
        batch_size = self.config.batch_size
        max_workers = self.config.max_concurrent_workers
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit episode generation tasks in batches
            for batch_start in range(0, total_episodes, batch_size):
                batch_end = min(batch_start + batch_size, total_episodes)
                batch_episodes = episodes[batch_start:batch_end]
                
                # Submit batch for processing
                future_to_episode = {}
                for episode in batch_episodes:
                    future = executor.submit(self._generate_episode_content, episode, deployment_path)
                    future_to_episode[future] = episode
                
                # Process completed tasks
                for future in as_completed(future_to_episode, timeout=self.config.timeout_seconds):
                    episode = future_to_episode[future]
                    try:
                        episode_result = future.result()
                        if episode_result:
                            counts.episodes += 1
                            counts.pages_generated += 1
                        
                        # Update progress
                        progress = (batch_end / total_episodes) * 0.6 + 0.1  # 10-70% range
                        self._report_progress(f"Generated {counts.episodes}/{total_episodes} episodes", progress)
                        
                    except Exception as e:
                        # Log error but continue with other episodes
                        print(f"Failed to generate episode {episode.episode_id}: {e}")
        
        # Generate series pages
        self._report_progress("Generating series pages", 0.7)
        series_list = self.content_registry.get_all_series()
        for series in series_list:
            series_episodes = [ep for ep in episodes if ep.series.series_id == series.series_id]
            if self._generate_series_content(series, series_episodes, deployment_path):
                counts.series += 1
                counts.pages_generated += 1
        
        # Generate host profiles
        self._report_progress("Generating host profiles", 0.75)
        hosts = self.content_registry.get_all_hosts()
        for host in hosts:
            host_episodes = [ep for ep in episodes if any(h.person_id == host.person_id for h in ep.hosts)]
            if self._generate_host_content(host, host_episodes, deployment_path):
                counts.hosts += 1
                counts.pages_generated += 1
        
        # Generate feeds
        self._report_progress("Generating feeds", 0.8)
        if self._generate_feeds(episodes, series_list, deployment_path):
            counts.feeds_generated = len(series_list) + 2  # Site RSS + sitemaps + per-series RSS
        
        # Generate social packages if enabled
        if self.config.social_validation_enabled:
            self._report_progress("Generating social packages", 0.85)
            social_counts = self._generate_social_packages(episodes, deployment_path)
            counts.social_packages = social_counts["total"]
            counts.social_packages_valid = social_counts["valid"]
        
        return counts
    
    def _generate_episode_content(self, episode: Episode, deployment_path: Path) -> bool:
        """Generate content for a single episode"""
        try:
            # Generate episode page
            episode_page = self.web_generator.generate_episode_page(episode)
            
            # Save HTML page
            episode_file = deployment_path / "episodes" / f"{episode.episode_id}.html"
            with open(episode_file, 'w', encoding='utf-8') as f:
                f.write(self.web_generator.render_complete_html(episode_page))
            
            # Save JSON-LD separately for validation
            if episode_page.json_ld:
                json_file = deployment_path / "episodes" / f"{episode.episode_id}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(episode_page.json_ld, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Failed to generate episode {episode.episode_id}: {e}")
            return False
    
    def _generate_series_content(self, series: Series, episodes: List[Episode], deployment_path: Path) -> bool:
        """Generate content for a series"""
        try:
            series_page = self.web_generator.generate_series_index(series, episodes)
            
            series_file = deployment_path / "series" / f"{series.slug}.html"
            with open(series_file, 'w', encoding='utf-8') as f:
                f.write(self.web_generator.render_complete_html(series_page))
            
            # Save JSON-LD
            if series_page.json_ld:
                json_file = deployment_path / "series" / f"{series.slug}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(series_page.json_ld, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Failed to generate series {series.series_id}: {e}")
            return False
    
    def _generate_host_content(self, host: Host, episodes: List[Episode], deployment_path: Path) -> bool:
        """Generate content for a host profile"""
        try:
            host_page = self.web_generator.generate_host_profile(host, episodes)
            
            host_file = deployment_path / "hosts" / f"{host.slug}.html"
            with open(host_file, 'w', encoding='utf-8') as f:
                f.write(self.web_generator.render_complete_html(host_page))
            
            # Save JSON-LD
            if host_page.json_ld:
                json_file = deployment_path / "hosts" / f"{host.slug}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(host_page.json_ld, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Failed to generate host {host.person_id}: {e}")
            return False
    
    def _generate_feeds(self, episodes: List[Episode], series_list: List[Series], deployment_path: Path) -> bool:
        """Generate RSS feeds and sitemaps"""
        try:
            feeds_path = deployment_path / "feeds"
            
            # Generate site-wide RSS feed
            site_rss = self.feed_generator.generate_site_rss(episodes)
            with open(feeds_path / "rss.xml", 'w', encoding='utf-8') as f:
                f.write(site_rss.to_xml())
            
            # Generate per-series RSS feeds
            for series in series_list:
                series_episodes = [ep for ep in episodes if ep.series.series_id == series.series_id]
                if series_episodes:
                    series_rss = self.feed_generator.generate_series_rss(series, series_episodes)
                    with open(feeds_path / f"series_{series.slug}.xml", 'w', encoding='utf-8') as f:
                        f.write(series_rss.to_xml())
            
            # Generate sitemaps
            all_urls = []
            
            # Add episode URLs
            for episode in episodes:
                all_urls.append(self.web_generator.url_patterns.generate_episode_url(episode))
            
            # Add series URLs
            for series in series_list:
                all_urls.append(self.web_generator.url_patterns.generate_series_url(series))
            
            # Generate XML sitemap
            sitemap = self.feed_generator.generate_sitemap(all_urls)
            with open(feeds_path / "sitemap.xml", 'w', encoding='utf-8') as f:
                f.write(sitemap.to_xml())
            
            # Generate video sitemap
            video_sitemap = self.feed_generator.generate_video_sitemap(episodes)
            with open(feeds_path / "video_sitemap.xml", 'w', encoding='utf-8') as f:
                f.write(video_sitemap.to_xml())
            
            # Generate news sitemap for recent episodes
            recent_episodes = [ep for ep in episodes 
                             if ep.upload_date > datetime.now() - timedelta(hours=48)]
            if recent_episodes:
                news_sitemap = self.feed_generator.generate_news_sitemap(recent_episodes)
                with open(feeds_path / "news_sitemap.xml", 'w', encoding='utf-8') as f:
                    f.write(news_sitemap.to_xml())
            
            return True
            
        except Exception as e:
            print(f"Failed to generate feeds: {e}")
            return False
    
    def _generate_social_packages(self, episodes: List[Episode], deployment_path: Path) -> Dict[str, int]:
        """Generate social media packages"""
        social_path = deployment_path / "social"
        total_packages = 0
        valid_packages = 0
        
        platforms = ["youtube", "instagram"]  # Configure as needed
        
        for episode in episodes:
            for platform in platforms:
                try:
                    package = self.social_generator.generate_social_package(episode, platform)
                    total_packages += 1
                    
                    # Validate package
                    validation_result = self.compliance_validator.validate_social_package(package)
                    if validation_result.is_valid:
                        valid_packages += 1
                        
                        # Save package
                        package_path = social_path / platform / episode.episode_id
                        package_path.mkdir(parents=True, exist_ok=True)
                        
                        # Save upload manifest
                        with open(package_path / "upload.json", 'w', encoding='utf-8') as f:
                            json.dump(package.upload_manifest.to_dict(), f, indent=2)
                    
                except Exception as e:
                    print(f"Failed to generate social package for {episode.episode_id} on {platform}: {e}")
                    total_packages += 1  # Count failed attempts
        
        return {"total": total_packages, "valid": valid_packages}
    
    def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentResult]:
        """Get status of a staging deployment"""
        deployment_path = self.staging_path / deployment_id
        
        if not deployment_path.exists():
            return None
        
        # Check if deployment is complete by looking for completion marker
        completion_marker = deployment_path / ".deployment_complete"
        if completion_marker.exists():
            status = DeploymentStatus.COMPLETED
        else:
            status = DeploymentStatus.IN_PROGRESS
        
        # Count generated content
        counts = ContentCounts()
        
        episodes_path = deployment_path / "episodes"
        if episodes_path.exists():
            counts.episodes = len(list(episodes_path.glob("*.html")))
            counts.pages_generated += counts.episodes
        
        series_path = deployment_path / "series"
        if series_path.exists():
            counts.series = len(list(series_path.glob("*.html")))
            counts.pages_generated += counts.series
        
        hosts_path = deployment_path / "hosts"
        if hosts_path.exists():
            counts.hosts = len(list(hosts_path.glob("*.html")))
            counts.pages_generated += counts.hosts
        
        feeds_path = deployment_path / "feeds"
        if feeds_path.exists():
            counts.feeds_generated = len(list(feeds_path.glob("*.xml")))
        
        return DeploymentResult(
            deployment_id=deployment_id,
            status=status,
            environment=Environment.STAGING,
            content_counts=counts,
            metadata={"staging_path": str(deployment_path)}
        )
    
    def cleanup_old_deployments(self, keep_count: int = 5) -> List[str]:
        """Clean up old staging deployments, keeping only the most recent"""
        if not self.staging_path.exists():
            return []
        
        # Get all deployment directories
        deployments = []
        for path in self.staging_path.iterdir():
            if path.is_dir() and path.name.startswith("staging_"):
                deployments.append(path)
        
        # Sort by creation time (newest first)
        deployments.sort(key=lambda p: p.stat().st_ctime, reverse=True)
        
        # Remove old deployments
        removed = []
        for deployment_path in deployments[keep_count:]:
            try:
                shutil.rmtree(deployment_path)
                removed.append(deployment_path.name)
            except Exception as e:
                print(f"Failed to remove old deployment {deployment_path.name}: {e}")
        
        return removed


# Utility functions

def create_staging_deployment(config: Optional[DeploymentConfig] = None) -> StagingDeployment:
    """
    Create a StagingDeployment instance with configuration
    
    Args:
        config: Optional deployment configuration
        
    Returns:
        Configured StagingDeployment instance
    """
    if config is None:
        config = DeploymentConfig()
    
    return StagingDeployment(config)


def validate_deployment_config(config: DeploymentConfig) -> List[str]:
    """
    Validate deployment configuration
    
    Args:
        config: Configuration to validate
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Validate batch size
    if config.batch_size <= 0:
        errors.append("Batch size must be positive")
    
    if config.batch_size > 1000:
        errors.append("Batch size should not exceed 1000 for memory efficiency")
    
    # Validate concurrency
    if config.max_concurrent_workers <= 0:
        errors.append("Max concurrent workers must be positive")
    
    if config.max_concurrent_workers > 20:
        errors.append("Max concurrent workers should not exceed 20")
    
    # Validate thresholds
    if not (0.0 <= config.schema_compliance_threshold <= 1.0):
        errors.append("Schema compliance threshold must be between 0.0 and 1.0")
    
    if not (0.0 <= config.feed_validation_threshold <= 1.0):
        errors.append("Feed validation threshold must be between 0.0 and 1.0")
    
    if not (0.0 <= config.social_package_failure_threshold <= 1.0):
        errors.append("Social package failure threshold must be between 0.0 and 1.0")
    
    # Validate paths
    for path_name, path_value in [
        ("staging_root", config.staging_root),
        ("production_root", config.production_root),
        ("backup_root", config.backup_root)
    ]:
        if not path_value:
            errors.append(f"{path_name} cannot be empty")
    
    return errors


class ValidationGateSystem:
    """
    Validation gate system with configurable thresholds and zero-tolerance enforcement
    
    Implements comprehensive validation gates for HTML structure, schema compliance,
    link integrity, feed validation, and social package compliance.
    """
    
    def __init__(self, config: DeploymentConfig):
        """
        Initialize validation gate system
        
        Args:
            config: Deployment configuration with validation thresholds
        """
        self.config = config
        
        # Initialize validators
        self.schema_validator = SchemaValidator()
        self.link_validator = LinkValidator()
        self.rss_validator = RSSFeedValidator()
        self.sitemap_validator = XMLSitemapValidator()
        self.compliance_validator = ComplianceValidator()
    
    def run_validation_gates(self, deployment_path: Path, manifest: PublishManifest) -> ValidationReport:
        """
        Run all validation gates on deployed content
        
        Args:
            deployment_path: Path to deployed content
            manifest: Publishing manifest
            
        Returns:
            ValidationReport with comprehensive validation results
        """
        gate_results = []
        
        # HTML Structure Gate
        html_result = self._run_html_structure_gate(deployment_path)
        gate_results.append(html_result)
        
        # Schema Compliance Gate
        schema_result = self._run_schema_compliance_gate(deployment_path)
        gate_results.append(schema_result)
        
        # Link Integrity Gate
        link_result = self._run_link_integrity_gate(deployment_path)
        gate_results.append(link_result)
        
        # Feed Validation Gate
        feed_result = self._run_feed_validation_gate(deployment_path)
        gate_results.append(feed_result)
        
        # Social Package Gate (if enabled)
        if self.config.social_validation_enabled:
            social_result = self._run_social_package_gate(deployment_path, manifest)
            gate_results.append(social_result)
        
        # Aggregate results
        overall_passed = all(result.passed for result in gate_results)
        
        # Handle social package gate in non-strict mode
        if not self.config.social_strict_mode:
            # Exclude social package failures from overall pass/fail
            non_social_results = [r for r in gate_results if r.gate_type != ValidationGateType.SOCIAL_PACKAGE]
            overall_passed = all(result.passed for result in non_social_results)
        
        total_errors = sum(len(result.errors) for result in gate_results)
        total_warnings = sum(len(result.warnings) for result in gate_results)
        
        return ValidationReport(
            overall_passed=overall_passed,
            gate_results=gate_results,
            total_errors=total_errors,
            total_warnings=total_warnings,
            validation_timestamp=datetime.now()
        )
    
    def _run_html_structure_gate(self, deployment_path: Path) -> ValidationGateResult:
        """Run HTML structure validation gate with zero tolerance for parse failures"""
        errors = []
        warnings = []
        total_files = 0
        parse_failures = 0
        
        # Find all HTML files
        html_files = []
        for pattern in ["episodes/*.html", "series/*.html", "hosts/*.html"]:
            html_files.extend(deployment_path.glob(pattern))
        
        total_files = len(html_files)
        
        for html_file in html_files:
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Validate HTML structure
                validation_result = self.schema_validator.validate_html_structure(html_content)
                
                if not validation_result.is_valid:
                    parse_failures += 1
                    for error in validation_result.errors:
                        error.location = f"{html_file.name}: {error.location}"
                        errors.append(error)
                
                # Add warnings
                for warning in validation_result.warnings:
                    warning.location = f"{html_file.name}: {warning.location}"
                    warnings.append(warning)
                
            except Exception as e:
                parse_failures += 1
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Failed to parse HTML file: {str(e)}",
                    location=str(html_file),
                    severity=Severity.ERROR
                ))
        
        # Calculate success rate
        success_rate = (total_files - parse_failures) / total_files if total_files > 0 else 1.0
        threshold = 1.0 - (self.config.html_parse_failure_threshold / max(total_files, 1))
        
        return ValidationGateResult(
            gate_type=ValidationGateType.HTML_STRUCTURE,
            passed=parse_failures <= self.config.html_parse_failure_threshold,
            threshold=threshold,
            actual_score=success_rate,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_files": total_files,
                "parse_failures": parse_failures,
                "success_rate": success_rate
            }
        )
    
    def _run_schema_compliance_gate(self, deployment_path: Path) -> ValidationGateResult:
        """Run JSON-LD schema compliance validation with 100% success requirement"""
        errors = []
        warnings = []
        total_files = 0
        compliance_failures = 0
        
        # Find all JSON-LD files
        json_files = []
        for pattern in ["episodes/*.json", "series/*.json", "hosts/*.json"]:
            json_files.extend(deployment_path.glob(pattern))
        
        total_files = len(json_files)
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_ld_data = json.load(f)
                
                # Validate JSON-LD schema
                validation_result = self.schema_validator.validate_json_ld(json_ld_data)
                
                if not validation_result.is_valid:
                    compliance_failures += 1
                    for error in validation_result.errors:
                        error.location = f"{json_file.name}: {error.location}"
                        errors.append(error)
                
                # Add warnings
                for warning in validation_result.warnings:
                    warning.location = f"{json_file.name}: {warning.location}"
                    warnings.append(warning)
                
            except Exception as e:
                compliance_failures += 1
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Failed to validate JSON-LD: {str(e)}",
                    location=str(json_file),
                    severity=Severity.ERROR
                ))
        
        # Calculate compliance rate
        compliance_rate = (total_files - compliance_failures) / total_files if total_files > 0 else 1.0
        
        return ValidationGateResult(
            gate_type=ValidationGateType.SCHEMA_COMPLIANCE,
            passed=compliance_rate >= self.config.schema_compliance_threshold,
            threshold=self.config.schema_compliance_threshold,
            actual_score=compliance_rate,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_files": total_files,
                "compliance_failures": compliance_failures,
                "compliance_rate": compliance_rate
            }
        )
    
    def _run_link_integrity_gate(self, deployment_path: Path) -> ValidationGateResult:
        """Run link integrity validation with zero broken link tolerance"""
        errors = []
        warnings = []
        
        # Collect all HTML pages for link validation
        html_pages = []
        
        # Load HTML files and extract links
        for pattern in ["episodes/*.html", "series/*.html", "hosts/*.html"]:
            for html_file in deployment_path.glob(pattern):
                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    html_pages.append({
                        "file_path": str(html_file),
                        "content": html_content,
                        "url": self._get_url_from_file_path(html_file)
                    })
                    
                except Exception as e:
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Failed to read HTML file: {str(e)}",
                        location=str(html_file),
                        severity=Severity.ERROR
                    ))
        
        # Run link validation
        if html_pages:
            validation_result = self.link_validator.check_internal_links(html_pages)
            
            # Process broken links
            broken_links = validation_result.metadata.get("broken_links", [])
            
            for broken_link in broken_links:
                errors.append(ValidationError(
                    error_type=ErrorType.SCHEMA_VALIDATION,
                    message=f"Broken internal link: {broken_link['url']}",
                    location=broken_link.get("source_file", "unknown"),
                    severity=Severity.ERROR
                ))
            
            # Add warnings for other issues
            for warning in validation_result.warnings:
                warnings.append(warning)
        
        broken_link_count = len([e for e in errors if "Broken internal link" in e.message])
        
        return ValidationGateResult(
            gate_type=ValidationGateType.LINK_INTEGRITY,
            passed=broken_link_count <= self.config.broken_link_threshold,
            threshold=float(self.config.broken_link_threshold),
            actual_score=float(broken_link_count),
            errors=errors,
            warnings=warnings,
            metadata={
                "total_pages": len(html_pages),
                "broken_links": broken_link_count
            }
        )
    
    def _run_feed_validation_gate(self, deployment_path: Path) -> ValidationGateResult:
        """Run RSS and XML sitemap validation against specifications"""
        errors = []
        warnings = []
        total_feeds = 0
        validation_failures = 0
        
        feeds_path = deployment_path / "feeds"
        
        if feeds_path.exists():
            # Validate RSS feeds
            for rss_file in feeds_path.glob("*.xml"):
                if "sitemap" not in rss_file.name.lower():  # Skip sitemaps for RSS validation
                    total_feeds += 1
                    try:
                        with open(rss_file, 'r', encoding='utf-8') as f:
                            rss_content = f.read()
                        
                        validation_result = self.rss_validator.validate_rss_feed(rss_content)
                        
                        if not validation_result.is_valid:
                            validation_failures += 1
                            for error in validation_result.errors:
                                error.location = f"{rss_file.name}: {error.location}"
                                errors.append(error)
                        
                        for warning in validation_result.warnings:
                            warning.location = f"{rss_file.name}: {warning.location}"
                            warnings.append(warning)
                        
                    except Exception as e:
                        validation_failures += 1
                        errors.append(ValidationError(
                            error_type=ErrorType.SCHEMA_VALIDATION,
                            message=f"Failed to validate RSS feed: {str(e)}",
                            location=str(rss_file),
                            severity=Severity.ERROR
                        ))
            
            # Validate XML sitemaps
            for sitemap_file in feeds_path.glob("*sitemap*.xml"):
                total_feeds += 1
                try:
                    with open(sitemap_file, 'r', encoding='utf-8') as f:
                        sitemap_content = f.read()
                    
                    validation_result = self.sitemap_validator.validate_sitemap(sitemap_content)
                    
                    if not validation_result.is_valid:
                        validation_failures += 1
                        for error in validation_result.errors:
                            error.location = f"{sitemap_file.name}: {error.location}"
                            errors.append(error)
                    
                    for warning in validation_result.warnings:
                        warning.location = f"{sitemap_file.name}: {warning.location}"
                        warnings.append(warning)
                    
                except Exception as e:
                    validation_failures += 1
                    errors.append(ValidationError(
                        error_type=ErrorType.SCHEMA_VALIDATION,
                        message=f"Failed to validate sitemap: {str(e)}",
                        location=str(sitemap_file),
                        severity=Severity.ERROR
                    ))
        
        # Calculate validation rate
        validation_rate = (total_feeds - validation_failures) / total_feeds if total_feeds > 0 else 1.0
        
        return ValidationGateResult(
            gate_type=ValidationGateType.FEED_VALIDATION,
            passed=validation_rate >= self.config.feed_validation_threshold,
            threshold=self.config.feed_validation_threshold,
            actual_score=validation_rate,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_feeds": total_feeds,
                "validation_failures": validation_failures,
                "validation_rate": validation_rate
            }
        )
    
    def _run_social_package_gate(self, deployment_path: Path, manifest: PublishManifest) -> ValidationGateResult:
        """Run social package validation with configurable failure threshold"""
        if not self.config.social_validation_enabled:
            return ValidationGateResult(
                gate_type=ValidationGateType.SOCIAL_PACKAGE,
                passed=True,
                threshold=self.config.social_package_failure_threshold,
                actual_score=0.0,
                errors=[],
                warnings=[],
                metadata={"validation_skipped": True}
            )
        
        errors = []
        warnings = []
        
        try:
            # Create content registry for social validation
            registry = ContentRegistry(str(deployment_path))
            
            # Load manifest if it exists
            manifest_path = deployment_path / "publish_manifest.json"
            if manifest_path.exists():
                registry.load_manifest(str(manifest_path))
            else:
                # Use provided manifest
                registry.manifest = manifest
            
            # Run comprehensive social package validation
            validation_result = registry.validate_social_packages(
                failure_threshold=self.config.social_package_failure_threshold
            )
            
            errors.extend(validation_result.errors)
            warnings.extend(validation_result.warnings)
            
            # Extract metadata
            metadata = validation_result.metadata
            total_packages = metadata.get("total_packages", 0)
            failed_packages = metadata.get("failed_packages", 0)
            failure_rate = metadata.get("failure_rate", 0.0)
            threshold_exceeded = metadata.get("threshold_exceeded", False)
            
            # Determine if gate passed
            gate_passed = validation_result.is_valid and not threshold_exceeded
            
            return ValidationGateResult(
                gate_type=ValidationGateType.SOCIAL_PACKAGE,
                passed=gate_passed,
                threshold=self.config.social_package_failure_threshold,
                actual_score=failure_rate,
                errors=errors,
                warnings=warnings,
                metadata={
                    "total_packages": total_packages,
                    "failed_packages": failed_packages,
                    "failure_rate": failure_rate,
                    "threshold_exceeded": threshold_exceeded,
                    "validation_enabled": True
                }
            )
            
        except Exception as e:
            # Fallback to basic validation if registry fails
            errors.append(ValidationError(
                error_type=ErrorType.PLATFORM_COMPLIANCE,
                message=f"Social package validation failed: {str(e)}",
                location="social_packages",
                severity=Severity.ERROR
            ))
            
            return ValidationGateResult(
                gate_type=ValidationGateType.SOCIAL_PACKAGE,
                passed=False,
                threshold=self.config.social_package_failure_threshold,
                actual_score=1.0,  # Assume 100% failure on exception
                errors=errors,
                warnings=warnings,
                metadata={
                    "validation_error": str(e),
                    "fallback_validation": True
                }
            )
    
    def _get_url_from_file_path(self, file_path: Path) -> str:
        """Convert file path to URL for link validation"""
        # This is a simplified implementation - in practice, you'd use the URL patterns
        relative_path = file_path.name.replace('.html', '')
        
        if 'episodes' in str(file_path):
            return f"/episodes/{relative_path}"
        elif 'series' in str(file_path):
            return f"/series/{relative_path}"
        elif 'hosts' in str(file_path):
            return f"/hosts/{relative_path}"
        else:
            return f"/{relative_path}"
    
    def validate_gate_configuration(self) -> List[str]:
        """
        Validate validation gate configuration
        
        Returns:
            List of configuration error messages
        """
        errors = []
        
        # Check threshold values
        if self.config.html_parse_failure_threshold < 0:
            errors.append("HTML parse failure threshold cannot be negative")
        
        if self.config.broken_link_threshold < 0:
            errors.append("Broken link threshold cannot be negative")
        
        if not (0.0 <= self.config.schema_compliance_threshold <= 1.0):
            errors.append("Schema compliance threshold must be between 0.0 and 1.0")
        
        if not (0.0 <= self.config.feed_validation_threshold <= 1.0):
            errors.append("Feed validation threshold must be between 0.0 and 1.0")
        
        if not (0.0 <= self.config.social_package_failure_threshold <= 1.0):
            errors.append("Social package failure threshold must be between 0.0 and 1.0")
        
        return errors
    
    def generate_validation_report_summary(self, report: ValidationReport) -> str:
        """
        Generate human-readable summary of validation report
        
        Args:
            report: ValidationReport to summarize
            
        Returns:
            Formatted summary string
        """
        summary_lines = []
        
        summary_lines.append(f"Validation Report - {report.validation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        summary_lines.append(f"Overall Status: {'PASSED' if report.overall_passed else 'FAILED'}")
        summary_lines.append(f"Total Errors: {report.total_errors}")
        summary_lines.append(f"Total Warnings: {report.total_warnings}")
        summary_lines.append("")
        
        # Gate-by-gate results
        for gate_result in report.gate_results:
            gate_name = gate_result.gate_type.value.replace('_', ' ').title()
            status = "PASSED" if gate_result.passed else "FAILED"
            
            summary_lines.append(f"{gate_name}: {status}")
            summary_lines.append(f"  Threshold: {gate_result.threshold:.2f}")
            summary_lines.append(f"  Actual: {gate_result.actual_score:.2f}")
            summary_lines.append(f"  Errors: {len(gate_result.errors)}")
            summary_lines.append(f"  Warnings: {len(gate_result.warnings)}")
            
            # Add metadata details
            if gate_result.metadata:
                for key, value in gate_result.metadata.items():
                    if key not in ['errors', 'warnings']:
                        summary_lines.append(f"  {key.replace('_', ' ').title()}: {value}")
            
            summary_lines.append("")
        
        return "\n".join(summary_lines)


# Utility functions for validation gates

def create_validation_gate_system(config: Optional[DeploymentConfig] = None) -> ValidationGateSystem:
    """
    Create a ValidationGateSystem instance with configuration
    
    Args:
        config: Optional deployment configuration
        
    Returns:
        Configured ValidationGateSystem instance
    """
    if config is None:
        config = DeploymentConfig()
    
    return ValidationGateSystem(config)


def create_zero_tolerance_config() -> DeploymentConfig:
    """
    Create deployment configuration with zero-tolerance validation settings
    
    Returns:
        DeploymentConfig with strict validation thresholds
    """
    return DeploymentConfig(
        html_parse_failure_threshold=0,
        broken_link_threshold=0,
        schema_compliance_threshold=1.0,
        feed_validation_threshold=1.0,
        social_package_failure_threshold=0.0,
        social_strict_mode=True
    )


def create_lenient_config() -> DeploymentConfig:
    """
    Create deployment configuration with more lenient validation settings
    
    Returns:
        DeploymentConfig with relaxed validation thresholds
    """
    return DeploymentConfig(
        html_parse_failure_threshold=5,
        broken_link_threshold=2,
        schema_compliance_threshold=0.95,
        feed_validation_threshold=0.95,
        social_package_failure_threshold=0.2,
        social_strict_mode=False
    )


class ProductionDeployment:
    """
    Production deployment system with validation gate enforcement and rollback capabilities
    
    Handles promotion from staging to production with comprehensive validation,
    automatic rollback on failures, and deployment history tracking.
    """
    
    def __init__(self, config: DeploymentConfig):
        """
        Initialize production deployment system
        
        Args:
            config: Deployment configuration
        """
        self.config = config
        self.production_path = Path(config.production_root)
        self.backup_path = Path(config.backup_root)
        
        # Initialize validation system
        self.validation_system = ValidationGateSystem(config)
        
        # Deployment history
        self.history_file = self.backup_path / "deployment_history.json"
        self.deployment_history: List[DeploymentHistory] = []
        self._load_deployment_history()
    
    def promote_to_production(self, staging_deployment_id: str, staging_path: Optional[Path] = None) -> DeploymentResult:
        """
        Promote staging deployment to production with validation gate enforcement
        
        Args:
            staging_deployment_id: ID of staging deployment to promote
            staging_path: Optional path to staging deployment (auto-detected if None)
            
        Returns:
            DeploymentResult with promotion status and details
        """
        production_deployment_id = f"prod_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Locate staging deployment
            if staging_path is None:
                staging_path = Path(self.config.staging_root) / staging_deployment_id
            
            if not staging_path.exists():
                raise ValueError(f"Staging deployment not found: {staging_deployment_id}")
            
            # Load manifest from staging
            manifest = self._load_manifest_from_staging(staging_path)
            
            # Create backup of current production
            backup_id = self._create_production_backup()
            
            # Run validation gates on staging content
            validation_report = self.validation_system.run_validation_gates(staging_path, manifest)
            
            if not validation_report.overall_passed:
                # Validation failed - do not promote
                return DeploymentResult(
                    deployment_id=production_deployment_id,
                    status=DeploymentStatus.FAILED,
                    environment=Environment.PRODUCTION,
                    content_counts=ContentCounts(),
                    validation_report=validation_report,
                    error_message="Validation gates failed - promotion blocked",
                    metadata={
                        "staging_deployment_id": staging_deployment_id,
                        "backup_id": backup_id,
                        "validation_summary": self.validation_system.generate_validation_report_summary(validation_report)
                    }
                )
            
            # Validation passed - proceed with promotion
            content_counts = self._promote_content_to_production(staging_path, production_deployment_id)
            
            # Record successful deployment
            deployment_history = DeploymentHistory(
                deployment_id=production_deployment_id,
                environment=Environment.PRODUCTION,
                status=DeploymentStatus.COMPLETED,
                deployed_at=datetime.now(),
                manifest_build_id=manifest.build_id,
                content_counts=content_counts
            )
            
            self._add_to_deployment_history(deployment_history)
            
            return DeploymentResult(
                deployment_id=production_deployment_id,
                status=DeploymentStatus.COMPLETED,
                environment=Environment.PRODUCTION,
                content_counts=content_counts,
                validation_report=validation_report,
                deployed_at=datetime.now(),
                completed_at=datetime.now(),
                rollback_available=True,
                metadata={
                    "staging_deployment_id": staging_deployment_id,
                    "backup_id": backup_id,
                    "manifest_build_id": manifest.build_id,
                    "manifest_version": manifest.manifest_version
                }
            )
            
        except Exception as e:
            # Promotion failed - attempt rollback if backup exists
            error_message = f"Production promotion failed: {str(e)}"
            
            try:
                if 'backup_id' in locals():
                    rollback_result = self.rollback_deployment(backup_id)
                    if rollback_result.status == DeploymentStatus.COMPLETED:
                        error_message += f" - Automatic rollback to {backup_id} successful"
                    else:
                        error_message += f" - Automatic rollback failed: {rollback_result.error_message}"
            except Exception as rollback_error:
                error_message += f" - Rollback attempt failed: {str(rollback_error)}"
            
            return DeploymentResult(
                deployment_id=production_deployment_id,
                status=DeploymentStatus.FAILED,
                environment=Environment.PRODUCTION,
                content_counts=ContentCounts(),
                error_message=error_message,
                metadata={
                    "staging_deployment_id": staging_deployment_id,
                    "error_type": type(e).__name__
                }
            )
    
    def rollback_deployment(self, target_deployment_id: Optional[str] = None) -> DeploymentResult:
        """
        Rollback production to a previous deployment state
        
        Args:
            target_deployment_id: ID of deployment to rollback to (latest if None)
            
        Returns:
            DeploymentResult with rollback status
        """
        rollback_deployment_id = f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Find target deployment
            if target_deployment_id is None:
                # Get latest successful deployment
                successful_deployments = [
                    h for h in self.deployment_history 
                    if h.status == DeploymentStatus.COMPLETED and h.environment == Environment.PRODUCTION
                ]
                
                if not successful_deployments:
                    raise ValueError("No successful deployments found for rollback")
                
                target_deployment = successful_deployments[-1]
                target_deployment_id = target_deployment.deployment_id
            else:
                target_deployment = next(
                    (h for h in self.deployment_history if h.deployment_id == target_deployment_id),
                    None
                )
                
                if not target_deployment:
                    raise ValueError(f"Target deployment not found: {target_deployment_id}")
            
            # Locate backup
            backup_path = self.backup_path / target_deployment_id
            if not backup_path.exists():
                raise ValueError(f"Backup not found for deployment: {target_deployment_id}")
            
            # Create backup of current state before rollback
            current_backup_id = self._create_production_backup()
            
            # Perform rollback
            self._restore_from_backup(backup_path)
            
            # Record rollback in history
            rollback_history = DeploymentHistory(
                deployment_id=rollback_deployment_id,
                environment=Environment.PRODUCTION,
                status=DeploymentStatus.COMPLETED,
                deployed_at=datetime.now(),
                manifest_build_id=target_deployment.manifest_build_id,
                content_counts=target_deployment.content_counts,
                rollback_from=target_deployment_id
            )
            
            self._add_to_deployment_history(rollback_history)
            
            return DeploymentResult(
                deployment_id=rollback_deployment_id,
                status=DeploymentStatus.COMPLETED,
                environment=Environment.PRODUCTION,
                content_counts=target_deployment.content_counts,
                deployed_at=datetime.now(),
                completed_at=datetime.now(),
                rollback_available=True,
                metadata={
                    "rollback_target": target_deployment_id,
                    "current_backup_id": current_backup_id,
                    "rollback_type": "manual" if target_deployment_id else "automatic"
                }
            )
            
        except Exception as e:
            return DeploymentResult(
                deployment_id=rollback_deployment_id,
                status=DeploymentStatus.FAILED,
                environment=Environment.PRODUCTION,
                content_counts=ContentCounts(),
                error_message=f"Rollback failed: {str(e)}",
                metadata={
                    "target_deployment_id": target_deployment_id,
                    "error_type": type(e).__name__
                }
            )
    
    def _load_manifest_from_staging(self, staging_path: Path) -> PublishManifest:
        """Load publish manifest from staging deployment"""
        # Look for manifest in staging deployment
        manifest_candidates = [
            staging_path / "publish_manifest.json",
            staging_path / ".." / ".." / "publish_manifest.json",  # Original location
        ]
        
        for manifest_path in manifest_candidates:
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                return PublishManifest.from_dict(manifest_data)
        
        raise ValueError("Publish manifest not found in staging deployment")
    
    def _create_production_backup(self) -> str:
        """Create backup of current production deployment"""
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir = self.backup_path / backup_id
        
        # Ensure backup directory exists
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy production content to backup
        if self.production_path.exists():
            # Copy all production content
            for item in self.production_path.iterdir():
                if item.is_dir():
                    shutil.copytree(item, backup_dir / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, backup_dir / item.name)
        
        # Clean up old backups
        self._cleanup_old_backups()
        
        return backup_id
    
    def _promote_content_to_production(self, staging_path: Path, deployment_id: str) -> ContentCounts:
        """Copy content from staging to production"""
        # Ensure production directory exists
        self.production_path.mkdir(parents=True, exist_ok=True)
        
        # Clear existing production content
        for item in self.production_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        
        # Copy staging content to production
        content_counts = ContentCounts()
        
        for item in staging_path.iterdir():
            if item.name.startswith('.'):
                continue  # Skip hidden files/directories
            
            target_path = self.production_path / item.name
            
            if item.is_dir():
                shutil.copytree(item, target_path, dirs_exist_ok=True)
                
                # Count content
                if item.name == "episodes":
                    content_counts.episodes = len(list(item.glob("*.html")))
                elif item.name == "series":
                    content_counts.series = len(list(item.glob("*.html")))
                elif item.name == "hosts":
                    content_counts.hosts = len(list(item.glob("*.html")))
                elif item.name == "feeds":
                    content_counts.feeds_generated = len(list(item.glob("*.xml")))
                elif item.name == "social":
                    # Count social packages
                    total_packages = 0
                    for platform_dir in item.iterdir():
                        if platform_dir.is_dir():
                            total_packages += len(list(platform_dir.iterdir()))
                    content_counts.social_packages = total_packages
            else:
                shutil.copy2(item, target_path)
        
        content_counts.pages_generated = content_counts.episodes + content_counts.series + content_counts.hosts
        
        return content_counts
    
    def _restore_from_backup(self, backup_path: Path) -> None:
        """Restore production from backup"""
        # Clear current production
        if self.production_path.exists():
            for item in self.production_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            self.production_path.mkdir(parents=True, exist_ok=True)
        
        # Restore from backup
        for item in backup_path.iterdir():
            target_path = self.production_path / item.name
            
            if item.is_dir():
                shutil.copytree(item, target_path, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target_path)
    
    def _load_deployment_history(self) -> None:
        """Load deployment history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                self.deployment_history = []
                for item in history_data:
                    # Convert datetime strings back to datetime objects
                    item['deployed_at'] = datetime.fromisoformat(item['deployed_at'])
                    
                    # Convert content_counts dict to ContentCounts object
                    content_counts_data = item.pop('content_counts', {})
                    content_counts = ContentCounts(**content_counts_data)
                    
                    # Create DeploymentHistory object
                    history_entry = DeploymentHistory(
                        content_counts=content_counts,
                        **item
                    )
                    self.deployment_history.append(history_entry)
                    
            except Exception as e:
                print(f"Failed to load deployment history: {e}")
                self.deployment_history = []
        else:
            self.deployment_history = []
    
    def _save_deployment_history(self) -> None:
        """Save deployment history to file"""
        try:
            # Ensure backup directory exists
            self.backup_path.mkdir(parents=True, exist_ok=True)
            
            # Convert to serializable format
            history_data = []
            for entry in self.deployment_history:
                entry_dict = {
                    'deployment_id': entry.deployment_id,
                    'environment': entry.environment.value,
                    'status': entry.status.value,
                    'deployed_at': entry.deployed_at.isoformat(),
                    'manifest_build_id': entry.manifest_build_id,
                    'content_counts': {
                        'episodes': entry.content_counts.episodes,
                        'series': entry.content_counts.series,
                        'hosts': entry.content_counts.hosts,
                        'pages_generated': entry.content_counts.pages_generated,
                        'feeds_generated': entry.content_counts.feeds_generated,
                        'social_packages': entry.content_counts.social_packages,
                        'social_packages_valid': entry.content_counts.social_packages_valid
                    }
                }
                
                if entry.rollback_from:
                    entry_dict['rollback_from'] = entry.rollback_from
                
                history_data.append(entry_dict)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Failed to save deployment history: {e}")
    
    def _add_to_deployment_history(self, entry: DeploymentHistory) -> None:
        """Add entry to deployment history"""
        self.deployment_history.append(entry)
        
        # Keep only recent history
        if len(self.deployment_history) > self.config.max_rollback_history:
            self.deployment_history = self.deployment_history[-self.config.max_rollback_history:]
        
        self._save_deployment_history()
    
    def _cleanup_old_backups(self) -> None:
        """Clean up old backup directories"""
        if not self.backup_path.exists():
            return
        
        # Get all backup directories
        backups = []
        for item in self.backup_path.iterdir():
            if item.is_dir() and item.name.startswith("backup_"):
                backups.append(item)
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda p: p.stat().st_ctime, reverse=True)
        
        # Remove old backups beyond the limit
        for backup_dir in backups[self.config.max_rollback_history:]:
            try:
                shutil.rmtree(backup_dir)
            except Exception as e:
                print(f"Failed to remove old backup {backup_dir.name}: {e}")
    
    def get_deployment_history(self, limit: Optional[int] = None) -> List[DeploymentHistory]:
        """
        Get deployment history
        
        Args:
            limit: Optional limit on number of entries to return
            
        Returns:
            List of DeploymentHistory entries (newest first)
        """
        history = sorted(self.deployment_history, key=lambda h: h.deployed_at, reverse=True)
        
        if limit:
            history = history[:limit]
        
        return history
    
    def get_rollback_candidates(self) -> List[DeploymentHistory]:
        """
        Get list of deployments that can be rolled back to
        
        Returns:
            List of successful production deployments
        """
        candidates = [
            h for h in self.deployment_history
            if (h.status == DeploymentStatus.COMPLETED and 
                h.environment == Environment.PRODUCTION and
                not h.rollback_from)  # Exclude rollback deployments
        ]
        
        # Sort by deployment time (newest first)
        candidates.sort(key=lambda h: h.deployed_at, reverse=True)
        
        return candidates
    
    def validate_rollback_target(self, deployment_id: str) -> ValidationResult:
        """
        Validate that a deployment can be rolled back to
        
        Args:
            deployment_id: Deployment ID to validate
            
        Returns:
            ValidationResult with rollback feasibility
        """
        errors = []
        warnings = []
        
        # Check if deployment exists in history
        target_deployment = next(
            (h for h in self.deployment_history if h.deployment_id == deployment_id),
            None
        )
        
        if not target_deployment:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Deployment not found in history: {deployment_id}",
                location="deployment_history",
                severity=Severity.ERROR
            ))
            
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        
        # Check if deployment was successful
        if target_deployment.status != DeploymentStatus.COMPLETED:
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Cannot rollback to failed deployment: {deployment_id}",
                location="deployment_status",
                severity=Severity.ERROR
            ))
        
        # Check if backup exists
        backup_path = self.backup_path / deployment_id
        if not backup_path.exists():
            errors.append(ValidationError(
                error_type=ErrorType.SCHEMA_VALIDATION,
                message=f"Backup not found for deployment: {deployment_id}",
                location="backup_storage",
                severity=Severity.ERROR
            ))
        
        # Check backup age
        if target_deployment.deployed_at < datetime.now() - timedelta(days=30):
            warnings.append(ValidationWarning(
                message=f"Rollback target is older than 30 days: {deployment_id}",
                location="deployment_age"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                "target_deployment": target_deployment.deployment_id,
                "target_date": target_deployment.deployed_at.isoformat(),
                "backup_exists": backup_path.exists()
            }
        )


class DeploymentPipeline:
    """
    Main deployment pipeline orchestrating staging, validation, and production deployment
    
    Coordinates the complete deployment workflow from staging through validation gates
    to production promotion with rollback capabilities.
    """
    
    def __init__(self, config: Optional[DeploymentConfig] = None, 
                 analytics_tracker: Optional[Any] = None):
        """
        Initialize deployment pipeline
        
        Args:
            config: Optional deployment configuration
            analytics_tracker: Optional analytics tracker for deployment monitoring
        """
        self.config = config or DeploymentConfig()
        self.analytics_tracker = analytics_tracker
        
        # Initialize subsystems
        self.staging_deployment = StagingDeployment(self.config)
        self.production_deployment = ProductionDeployment(self.config)
        self.validation_system = ValidationGateSystem(self.config)
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[str, float], None]] = None
    
    def set_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """Set callback for progress reporting"""
        self.progress_callback = callback
        self.staging_deployment.set_progress_callback(callback)
    
    def deploy_full_pipeline(self, manifest_path: str, auto_promote: bool = False) -> Dict[str, DeploymentResult]:
        """
        Execute complete deployment pipeline from staging to production
        
        Args:
            manifest_path: Path to publish manifest
            auto_promote: Whether to automatically promote to production if validation passes
            
        Returns:
            Dictionary with staging and production deployment results
        """
        results = {}
        build_id = f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Start analytics tracking if available
        if self.analytics_tracker:
            manifest = self.staging_deployment.content_registry.load_manifest(manifest_path)
            content_counts = {
                "episodes": len(manifest.episodes),
                "series": len(manifest.series),
                "hosts": len(manifest.hosts)
            }
            self.analytics_tracker.start_deployment_tracking(build_id, content_counts)
        
        try:
            # Stage 1: Deploy to staging
            if self.progress_callback:
                self.progress_callback("Starting staging deployment", 0.0)
            
            staging_result = self.staging_deployment.deploy_to_staging(manifest_path)
            results['staging'] = staging_result
            
            # Update analytics with staging results
            if self.analytics_tracker:
                errors = [error.message for error in staging_result.errors] if staging_result.errors else []
                warnings = [warning.message for warning in staging_result.warnings] if staging_result.warnings else []
                self.analytics_tracker.update_deployment_metrics(build_id, errors=errors, warnings=warnings)
            
            if staging_result.status != DeploymentStatus.COMPLETED:
                # Complete analytics tracking with failure
                if self.analytics_tracker:
                    self.analytics_tracker.complete_deployment_tracking(build_id, False)
                return results
            
            # Stage 2: Run validation gates
            if self.progress_callback:
                self.progress_callback("Running validation gates", 0.5)
            
            staging_path = Path(self.config.staging_root) / staging_result.deployment_id
            manifest = self.staging_deployment.content_registry.load_manifest(manifest_path)
            
            validation_report = self.validation_system.run_validation_gates(staging_path, manifest)
            
            # Update staging result with validation report
            staging_result.validation_report = validation_report
            
            # Update analytics with validation results
            if self.analytics_tracker:
                validation_errors = [error.message for error in validation_report.errors]
                validation_warnings = [warning.message for warning in validation_report.warnings]
                self.analytics_tracker.update_deployment_metrics(
                    build_id, 
                    errors=validation_errors, 
                    warnings=validation_warnings
                )
            
            # Stage 3: Promote to production (if auto_promote and validation passed)
            production_success = True
            if auto_promote and validation_report.overall_passed:
                if self.progress_callback:
                    self.progress_callback("Promoting to production", 0.8)
                
                production_result = self.production_deployment.promote_to_production(
                    staging_result.deployment_id, staging_path
                )
                results['production'] = production_result
                production_success = production_result.status == DeploymentStatus.COMPLETED
                
                # Update analytics with production results
                if self.analytics_tracker:
                    prod_errors = [error.message for error in production_result.errors] if production_result.errors else []
                    prod_warnings = [warning.message for warning in production_result.warnings] if production_result.warnings else []
                    self.analytics_tracker.update_deployment_metrics(
                        build_id, 
                        errors=prod_errors, 
                        warnings=prod_warnings
                    )
            
            # Complete analytics tracking
            overall_success = (staging_result.status == DeploymentStatus.COMPLETED and 
                             validation_report.overall_passed and 
                             production_success)
            
            if self.analytics_tracker:
                self.analytics_tracker.complete_deployment_tracking(build_id, overall_success)
            
            if self.progress_callback:
                self.progress_callback("Pipeline complete", 1.0)
            
            return results
            
        except Exception as e:
            # Handle unexpected errors
            if self.analytics_tracker:
                self.analytics_tracker.update_deployment_metrics(
                    build_id, 
                    errors=[f"Pipeline error: {str(e)}"]
                )
                self.analytics_tracker.complete_deployment_tracking(build_id, False)
            raise
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get overall pipeline status and statistics
        
        Returns:
            Dictionary with pipeline status information
        """
        # Get recent deployment history
        recent_deployments = self.production_deployment.get_deployment_history(limit=10)
        
        # Calculate success rates
        total_deployments = len(recent_deployments)
        successful_deployments = len([d for d in recent_deployments if d.status == DeploymentStatus.COMPLETED])
        success_rate = successful_deployments / total_deployments if total_deployments > 0 else 0.0
        
        # Get rollback candidates
        rollback_candidates = self.production_deployment.get_rollback_candidates()
        
        return {
            "config": {
                "batch_size": self.config.batch_size,
                "max_concurrent_workers": self.config.max_concurrent_workers,
                "social_validation_enabled": self.config.social_validation_enabled,
                "social_strict_mode": self.config.social_strict_mode
            },
            "statistics": {
                "total_deployments": total_deployments,
                "successful_deployments": successful_deployments,
                "success_rate": success_rate,
                "rollback_candidates": len(rollback_candidates)
            },
            "recent_deployments": [
                {
                    "deployment_id": d.deployment_id,
                    "environment": d.environment.value,
                    "status": d.status.value,
                    "deployed_at": d.deployed_at.isoformat(),
                    "content_counts": {
                        "episodes": d.content_counts.episodes,
                        "series": d.content_counts.series,
                        "hosts": d.content_counts.hosts,
                        "pages_generated": d.content_counts.pages_generated
                    }
                }
                for d in recent_deployments[:5]  # Show last 5
            ],
            "validation_thresholds": {
                "html_parse_failure_threshold": self.config.html_parse_failure_threshold,
                "broken_link_threshold": self.config.broken_link_threshold,
                "schema_compliance_threshold": self.config.schema_compliance_threshold,
                "feed_validation_threshold": self.config.feed_validation_threshold,
                "social_package_failure_threshold": self.config.social_package_failure_threshold
            }
        }


# Utility functions for production deployment

def create_deployment_pipeline(config: Optional[DeploymentConfig] = None) -> DeploymentPipeline:
    """
    Create a DeploymentPipeline instance with configuration
    
    Args:
        config: Optional deployment configuration
        
    Returns:
        Configured DeploymentPipeline instance
    """
    return DeploymentPipeline(config)


def create_production_deployment(config: Optional[DeploymentConfig] = None) -> ProductionDeployment:
    """
    Create a ProductionDeployment instance with configuration
    
    Args:
        config: Optional deployment configuration
        
    Returns:
        Configured ProductionDeployment instance
    """
    if config is None:
        config = DeploymentConfig()
    
    return ProductionDeployment(config)