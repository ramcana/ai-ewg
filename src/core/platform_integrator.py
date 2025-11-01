"""
Platform Integrator for external platform connections

Handles search engine integration, social posting queue, and platform API integration
for the Content Publishing Platform.
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urljoin, urlparse

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .publishing_models import (
    SocialPackage, ValidationResult, ValidationError, ErrorType, Severity,
    PackageStatus, PrivacyLevel, AssetType
)


logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """Types of external platforms"""
    SEARCH_ENGINE = "search_engine"
    SOCIAL_MEDIA = "social_media"
    NEWS_PLATFORM = "news_platform"


class SubmissionStatus(Enum):
    """Status of platform submissions"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    FAILED = "failed"
    RETRYING = "retrying"


class ErrorClassification(Enum):
    """Classification of API errors"""
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXCEEDED = "quota_exceeded"


@dataclass
class PlatformCredentials:
    """Platform authentication credentials"""
    platform_name: str
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    verification_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if credentials are expired"""
        if not self.expires_at:
            return False
        return datetime.now() >= self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'platform_name': self.platform_name,
            'api_key': self.api_key,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'verification_token': self.verification_token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlatformCredentials':
        return cls(
            platform_name=data['platform_name'],
            api_key=data.get('api_key'),
            client_id=data.get('client_id'),
            client_secret=data.get('client_secret'),
            access_token=data.get('access_token'),
            refresh_token=data.get('refresh_token'),
            verification_token=data.get('verification_token'),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        )


@dataclass
class SubmissionResult:
    """Result of platform submission"""
    platform: str
    status: SubmissionStatus
    submission_id: Optional[str] = None
    message: Optional[str] = None
    submitted_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    error_details: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'platform': self.platform,
            'status': self.status.value,
            'submission_id': self.submission_id,
            'message': self.message,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'error_details': self.error_details,
            'retry_count': self.retry_count,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubmissionResult':
        return cls(
            platform=data['platform'],
            status=SubmissionStatus(data['status']),
            submission_id=data.get('submission_id'),
            message=data.get('message'),
            submitted_at=datetime.fromisoformat(data['submitted_at']) if data.get('submitted_at') else None,
            verified_at=datetime.fromisoformat(data['verified_at']) if data.get('verified_at') else None,
            error_details=data.get('error_details'),
            retry_count=data.get('retry_count', 0),
            next_retry_at=datetime.fromisoformat(data['next_retry_at']) if data.get('next_retry_at') else None
        )


@dataclass
class VerificationResult:
    """Result of domain ownership verification"""
    platform: str
    domain: str
    is_verified: bool
    verification_method: Optional[str] = None
    verification_token: Optional[str] = None
    verified_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'platform': self.platform,
            'domain': self.domain,
            'is_verified': self.is_verified,
            'verification_method': self.verification_method,
            'verification_token': self.verification_token,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'error_message': self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VerificationResult':
        return cls(
            platform=data['platform'],
            domain=data['domain'],
            is_verified=data['is_verified'],
            verification_method=data.get('verification_method'),
            verification_token=data.get('verification_token'),
            verified_at=datetime.fromisoformat(data['verified_at']) if data.get('verified_at') else None,
            error_message=data.get('error_message')
        )


class PlatformAPIClient(ABC):
    """Abstract base class for platform API clients"""
    
    def __init__(self, credentials: PlatformCredentials, base_url: str):
        self.credentials = credentials
        self.base_url = base_url
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry configuration"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the platform"""
        pass
    
    @abstractmethod
    def submit_sitemap(self, sitemap_url: str) -> SubmissionResult:
        """Submit sitemap to platform"""
        pass
    
    @abstractmethod
    def verify_domain_ownership(self, domain: str) -> VerificationResult:
        """Verify domain ownership"""
        pass
    
    def _classify_error(self, response: requests.Response) -> ErrorClassification:
        """Classify API error for retry logic"""
        status_code = response.status_code
        
        if status_code == 401:
            return ErrorClassification.AUTHENTICATION
        elif status_code == 429:
            return ErrorClassification.RATE_LIMIT
        elif status_code == 403:
            # Could be quota exceeded or permissions
            try:
                error_data = response.json()
                if 'quota' in str(error_data).lower():
                    return ErrorClassification.QUOTA_EXCEEDED
            except:
                pass
            return ErrorClassification.NON_RETRYABLE
        elif 500 <= status_code < 600:
            return ErrorClassification.RETRYABLE
        else:
            return ErrorClassification.NON_RETRYABLE
    
    def _calculate_backoff_delay(self, retry_count: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay"""
        return min(base_delay * (2 ** retry_count), 300)  # Max 5 minutes


class GoogleSearchConsoleClient(PlatformAPIClient):
    """Google Search Console API client"""
    
    def __init__(self, credentials: PlatformCredentials):
        super().__init__(credentials, "https://www.googleapis.com/webmasters/v3")
        self.site_url = None
    
    def authenticate(self) -> bool:
        """Authenticate with Google Search Console API"""
        if not self.credentials.access_token:
            logger.error("No access token provided for Google Search Console")
            return False
        
        # Test authentication with a simple API call
        try:
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = self.session.get(
                f"{self.base_url}/sites",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Successfully authenticated with Google Search Console")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def submit_sitemap(self, sitemap_url: str) -> SubmissionResult:
        """Submit sitemap to Google Search Console"""
        if not self.site_url:
            return SubmissionResult(
                platform="google_search_console",
                status=SubmissionStatus.FAILED,
                message="Site URL not configured",
                submitted_at=datetime.now()
            )
        
        try:
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Submit sitemap
            url = f"{self.base_url}/sites/{self.site_url}/sitemaps/{sitemap_url}"
            response = self.session.put(url, headers=headers, timeout=30)
            
            if response.status_code in [200, 204]:
                return SubmissionResult(
                    platform="google_search_console",
                    status=SubmissionStatus.SUBMITTED,
                    submission_id=sitemap_url,
                    message="Sitemap submitted successfully",
                    submitted_at=datetime.now()
                )
            else:
                error_classification = self._classify_error(response)
                return SubmissionResult(
                    platform="google_search_console",
                    status=SubmissionStatus.FAILED,
                    message=f"Submission failed: {response.status_code}",
                    submitted_at=datetime.now(),
                    error_details={
                        'status_code': response.status_code,
                        'response': response.text,
                        'classification': error_classification.value
                    }
                )
                
        except Exception as e:
            logger.error(f"Sitemap submission error: {e}")
            return SubmissionResult(
                platform="google_search_console",
                status=SubmissionStatus.FAILED,
                message=f"Submission error: {str(e)}",
                submitted_at=datetime.now()
            )
    
    def verify_domain_ownership(self, domain: str) -> VerificationResult:
        """Verify domain ownership with Google Search Console"""
        try:
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Check if site is already verified
            site_url = f"https://{domain}/"
            url = f"{self.base_url}/sites/{site_url}"
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                site_data = response.json()
                permission_level = site_data.get('permissionLevel', '')
                
                if permission_level in ['siteOwner', 'siteFullUser']:
                    self.site_url = site_url
                    return VerificationResult(
                        platform="google_search_console",
                        domain=domain,
                        is_verified=True,
                        verification_method="existing",
                        verified_at=datetime.now()
                    )
            
            # If not verified, return verification token for manual setup
            return VerificationResult(
                platform="google_search_console",
                domain=domain,
                is_verified=False,
                verification_method="meta_tag",
                verification_token=self.credentials.verification_token,
                error_message="Domain not verified. Add verification meta tag to site."
            )
            
        except Exception as e:
            logger.error(f"Domain verification error: {e}")
            return VerificationResult(
                platform="google_search_console",
                domain=domain,
                is_verified=False,
                error_message=f"Verification error: {str(e)}"
            )


class BingWebmasterToolsClient(PlatformAPIClient):
    """Bing Webmaster Tools API client"""
    
    def __init__(self, credentials: PlatformCredentials):
        super().__init__(credentials, "https://ssl.bing.com/webmaster/api.svc/json")
        self.site_url = None
    
    def authenticate(self) -> bool:
        """Authenticate with Bing Webmaster Tools API"""
        if not self.credentials.api_key:
            logger.error("No API key provided for Bing Webmaster Tools")
            return False
        
        # Test authentication
        try:
            params = {'apikey': self.credentials.api_key}
            response = self.session.get(
                f"{self.base_url}/GetUserSites",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Successfully authenticated with Bing Webmaster Tools")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def submit_sitemap(self, sitemap_url: str) -> SubmissionResult:
        """Submit sitemap to Bing Webmaster Tools"""
        if not self.site_url:
            return SubmissionResult(
                platform="bing_webmaster_tools",
                status=SubmissionStatus.FAILED,
                message="Site URL not configured",
                submitted_at=datetime.now()
            )
        
        try:
            params = {
                'apikey': self.credentials.api_key,
                'siteUrl': self.site_url,
                'feedUrl': sitemap_url
            }
            
            response = self.session.post(
                f"{self.base_url}/SubmitFeed",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return SubmissionResult(
                    platform="bing_webmaster_tools",
                    status=SubmissionStatus.SUBMITTED,
                    submission_id=sitemap_url,
                    message="Sitemap submitted successfully",
                    submitted_at=datetime.now()
                )
            else:
                error_classification = self._classify_error(response)
                return SubmissionResult(
                    platform="bing_webmaster_tools",
                    status=SubmissionStatus.FAILED,
                    message=f"Submission failed: {response.status_code}",
                    submitted_at=datetime.now(),
                    error_details={
                        'status_code': response.status_code,
                        'response': response.text,
                        'classification': error_classification.value
                    }
                )
                
        except Exception as e:
            logger.error(f"Sitemap submission error: {e}")
            return SubmissionResult(
                platform="bing_webmaster_tools",
                status=SubmissionStatus.FAILED,
                message=f"Submission error: {str(e)}",
                submitted_at=datetime.now()
            )
    
    def verify_domain_ownership(self, domain: str) -> VerificationResult:
        """Verify domain ownership with Bing Webmaster Tools"""
        try:
            params = {'apikey': self.credentials.api_key}
            response = self.session.get(
                f"{self.base_url}/GetUserSites",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                sites_data = response.json()
                sites = sites_data.get('d', [])
                
                # Check if domain is in user's sites
                for site in sites:
                    site_url = site.get('Url', '')
                    if domain in site_url:
                        self.site_url = site_url
                        return VerificationResult(
                            platform="bing_webmaster_tools",
                            domain=domain,
                            is_verified=True,
                            verification_method="existing",
                            verified_at=datetime.now()
                        )
            
            # If not verified, return instructions
            return VerificationResult(
                platform="bing_webmaster_tools",
                domain=domain,
                is_verified=False,
                verification_method="xml_file",
                verification_token=self.credentials.verification_token,
                error_message="Domain not verified. Add verification XML file to site root."
            )
            
        except Exception as e:
            logger.error(f"Domain verification error: {e}")
            return VerificationResult(
                platform="bing_webmaster_tools",
                domain=domain,
                is_verified=False,
                error_message=f"Verification error: {str(e)}"
            )


class SearchEngineIntegrator:
    """Search engine integration manager"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.clients: Dict[str, PlatformAPIClient] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize search engine API clients"""
        # Google Search Console
        if 'google_search_console' in self.config:
            gsc_config = self.config['google_search_console']
            credentials = PlatformCredentials(
                platform_name="google_search_console",
                access_token=gsc_config.get('access_token'),
                verification_token=gsc_config.get('verification_token')
            )
            self.clients['google_search_console'] = GoogleSearchConsoleClient(credentials)
        
        # Bing Webmaster Tools
        if 'bing_webmaster_tools' in self.config:
            bing_config = self.config['bing_webmaster_tools']
            credentials = PlatformCredentials(
                platform_name="bing_webmaster_tools",
                api_key=bing_config.get('api_key'),
                verification_token=bing_config.get('verification_token')
            )
            self.clients['bing_webmaster_tools'] = BingWebmasterToolsClient(credentials)
    
    def authenticate_all(self) -> Dict[str, bool]:
        """Authenticate with all configured search engines"""
        results = {}
        for platform, client in self.clients.items():
            try:
                results[platform] = client.authenticate()
            except Exception as e:
                logger.error(f"Authentication failed for {platform}: {e}")
                results[platform] = False
        return results
    
    def submit_sitemap_to_all(self, sitemap_url: str) -> Dict[str, SubmissionResult]:
        """Submit sitemap to all configured search engines"""
        results = {}
        for platform, client in self.clients.items():
            try:
                results[platform] = client.submit_sitemap(sitemap_url)
            except Exception as e:
                logger.error(f"Sitemap submission failed for {platform}: {e}")
                results[platform] = SubmissionResult(
                    platform=platform,
                    status=SubmissionStatus.FAILED,
                    message=f"Submission error: {str(e)}",
                    submitted_at=datetime.now()
                )
        return results
    
    def verify_domain_ownership_all(self, domain: str) -> Dict[str, VerificationResult]:
        """Verify domain ownership with all configured search engines"""
        results = {}
        for platform, client in self.clients.items():
            try:
                results[platform] = client.verify_domain_ownership(domain)
            except Exception as e:
                logger.error(f"Domain verification failed for {platform}: {e}")
                results[platform] = VerificationResult(
                    platform=platform,
                    domain=domain,
                    is_verified=False,
                    error_message=f"Verification error: {str(e)}"
                )
        return results
    
    def get_verification_status(self, domain: str) -> Dict[str, bool]:
        """Get verification status for domain across all platforms"""
        verification_results = self.verify_domain_ownership_all(domain)
        return {
            platform: result.is_verified 
            for platform, result in verification_results.items()
        }


def create_search_engine_integrator(config: Dict[str, Any]) -> SearchEngineIntegrator:
    """Factory function to create SearchEngineIntegrator"""
    return SearchEngineIntegrator(config)


@dataclass
class QueueItem:
    """Social posting queue item"""
    episode_id: str
    platform: str
    package_path: str
    suggested_publish_at: datetime
    priority: int = 0
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    external_id: Optional[str] = None
    status: str = "queued"  # queued, scheduled, posted, failed
    retry_count: int = 0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode_id': self.episode_id,
            'platform': self.platform,
            'package_path': self.package_path,
            'suggested_publish_at': self.suggested_publish_at.isoformat(),
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'posted_at': self.posted_at.isoformat() if self.posted_at else None,
            'external_id': self.external_id,
            'status': self.status,
            'retry_count': self.retry_count,
            'error_message': self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueItem':
        return cls(
            episode_id=data['episode_id'],
            platform=data['platform'],
            package_path=data['package_path'],
            suggested_publish_at=datetime.fromisoformat(data['suggested_publish_at']),
            priority=data.get('priority', 0),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            scheduled_at=datetime.fromisoformat(data['scheduled_at']) if data.get('scheduled_at') else None,
            posted_at=datetime.fromisoformat(data['posted_at']) if data.get('posted_at') else None,
            external_id=data.get('external_id'),
            status=data.get('status', 'queued'),
            retry_count=data.get('retry_count', 0),
            error_message=data.get('error_message')
        )


@dataclass
class PostingReceipt:
    """Receipt for successful social media posting"""
    episode_id: str
    platform: str
    external_id: str
    posted_at: datetime
    platform_url: Optional[str] = None
    platform_response: Optional[Dict[str, Any]] = None
    analytics_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode_id': self.episode_id,
            'platform': self.platform,
            'external_id': self.external_id,
            'posted_at': self.posted_at.isoformat(),
            'platform_url': self.platform_url,
            'platform_response': self.platform_response,
            'analytics_data': self.analytics_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PostingReceipt':
        return cls(
            episode_id=data['episode_id'],
            platform=data['platform'],
            external_id=data['external_id'],
            posted_at=datetime.fromisoformat(data['posted_at']),
            platform_url=data.get('platform_url'),
            platform_response=data.get('platform_response'),
            analytics_data=data.get('analytics_data')
        )


@dataclass
class QueueResult:
    """Result of queue operations"""
    success: bool
    message: str
    queue_item: Optional[QueueItem] = None
    error_details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'queue_item': self.queue_item.to_dict() if self.queue_item else None,
            'error_details': self.error_details
        }


@dataclass
class PostResult:
    """Result of social media posting"""
    success: bool
    platform: str
    episode_id: str
    external_id: Optional[str] = None
    platform_url: Optional[str] = None
    message: Optional[str] = None
    error_classification: Optional[ErrorClassification] = None
    retry_after: Optional[datetime] = None
    platform_response: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'platform': self.platform,
            'episode_id': self.episode_id,
            'external_id': self.external_id,
            'platform_url': self.platform_url,
            'message': self.message,
            'error_classification': self.error_classification.value if self.error_classification else None,
            'retry_after': self.retry_after.isoformat() if self.retry_after else None,
            'platform_response': self.platform_response
        }


class SocialPostingQueue:
    """Social media posting queue with build-based organization"""
    
    def __init__(self, queue_root: Path, max_retries: int = 3):
        self.queue_root = Path(queue_root)
        self.max_retries = max_retries
        self.queue_root.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.queue_root / "active").mkdir(exist_ok=True)
        (self.queue_root / "completed").mkdir(exist_ok=True)
        (self.queue_root / "failed").mkdir(exist_ok=True)
        (self.queue_root / "receipts").mkdir(exist_ok=True)
    
    def create_queue_from_build(self, build_id: str, social_packages: List[SocialPackage]) -> QueueResult:
        """Create queue file from social packages for a build"""
        try:
            queue_items = []
            
            for package in social_packages:
                if package.status != PackageStatus.VALID:
                    logger.warning(f"Skipping invalid package: {package.episode_id}/{package.platform}")
                    continue
                
                # Calculate suggested publish time (could be immediate or scheduled)
                suggested_time = package.upload_manifest.publish_at
                
                queue_item = QueueItem(
                    episode_id=package.episode_id,
                    platform=package.platform,
                    package_path=str(Path("social") / package.platform / package.episode_id),
                    suggested_publish_at=suggested_time,
                    priority=self._calculate_priority(package)
                )
                
                queue_items.append(queue_item)
            
            # Save queue file
            queue_file = self.queue_root / "active" / f"{build_id}.json"
            queue_data = {
                'build_id': build_id,
                'created_at': datetime.now().isoformat(),
                'total_items': len(queue_items),
                'items': [item.to_dict() for item in queue_items]
            }
            
            with open(queue_file, 'w') as f:
                json.dump(queue_data, f, indent=2)
            
            logger.info(f"Created queue file for build {build_id} with {len(queue_items)} items")
            
            return QueueResult(
                success=True,
                message=f"Queue created with {len(queue_items)} items",
                queue_item=None
            )
            
        except Exception as e:
            logger.error(f"Failed to create queue for build {build_id}: {e}")
            return QueueResult(
                success=False,
                message=f"Queue creation failed: {str(e)}",
                error_details={'exception': str(e)}
            )
    
    def _calculate_priority(self, package: SocialPackage) -> int:
        """Calculate posting priority for package"""
        priority = 0
        
        # Higher priority for newer content
        age_hours = (datetime.now() - package.created_at).total_seconds() / 3600
        if age_hours < 1:
            priority += 10
        elif age_hours < 24:
            priority += 5
        
        # Platform-specific priorities
        platform_priorities = {
            'youtube': 10,
            'instagram': 8,
            'tiktok': 6,
            'twitter': 4
        }
        priority += platform_priorities.get(package.platform, 0)
        
        return priority
    
    def get_pending_items(self, platform: Optional[str] = None, limit: Optional[int] = None) -> List[QueueItem]:
        """Get pending queue items, optionally filtered by platform"""
        pending_items = []
        
        # Scan active queue files
        for queue_file in (self.queue_root / "active").glob("*.json"):
            try:
                with open(queue_file, 'r') as f:
                    queue_data = json.load(f)
                
                for item_data in queue_data.get('items', []):
                    item = QueueItem.from_dict(item_data)
                    
                    # Filter by platform if specified
                    if platform and item.platform != platform:
                        continue
                    
                    # Only include queued or failed items that can be retried
                    if item.status == 'queued' or (item.status == 'failed' and item.retry_count < self.max_retries):
                        pending_items.append(item)
                
            except Exception as e:
                logger.error(f"Error reading queue file {queue_file}: {e}")
        
        # Sort by priority and suggested publish time
        pending_items.sort(key=lambda x: (-x.priority, x.suggested_publish_at))
        
        if limit:
            pending_items = pending_items[:limit]
        
        return pending_items
    
    def update_item_status(self, episode_id: str, platform: str, status: str, 
                          external_id: Optional[str] = None, error_message: Optional[str] = None) -> bool:
        """Update status of queue item"""
        try:
            # Find and update item in active queue files
            for queue_file in (self.queue_root / "active").glob("*.json"):
                with open(queue_file, 'r') as f:
                    queue_data = json.load(f)
                
                updated = False
                for item_data in queue_data.get('items', []):
                    if item_data['episode_id'] == episode_id and item_data['platform'] == platform:
                        item_data['status'] = status
                        
                        if status == 'posted':
                            item_data['posted_at'] = datetime.now().isoformat()
                            if external_id:
                                item_data['external_id'] = external_id
                        elif status == 'failed':
                            item_data['retry_count'] = item_data.get('retry_count', 0) + 1
                            if error_message:
                                item_data['error_message'] = error_message
                        
                        updated = True
                        break
                
                if updated:
                    with open(queue_file, 'w') as f:
                        json.dump(queue_data, f, indent=2)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating queue item status: {e}")
            return False
    
    def create_posting_receipt(self, episode_id: str, platform: str, external_id: str, 
                             platform_url: Optional[str] = None, 
                             platform_response: Optional[Dict[str, Any]] = None) -> PostingReceipt:
        """Create and store posting receipt"""
        receipt = PostingReceipt(
            episode_id=episode_id,
            platform=platform,
            external_id=external_id,
            posted_at=datetime.now(),
            platform_url=platform_url,
            platform_response=platform_response
        )
        
        # Save receipt to file
        receipt_file = self.queue_root / "receipts" / f"{episode_id}_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(receipt_file, 'w') as f:
                json.dump(receipt.to_dict(), f, indent=2)
            
            logger.info(f"Created posting receipt for {episode_id}/{platform}: {external_id}")
            
        except Exception as e:
            logger.error(f"Error saving posting receipt: {e}")
        
        return receipt
    
    def get_posting_receipts(self, episode_id: Optional[str] = None, 
                           platform: Optional[str] = None) -> List[PostingReceipt]:
        """Get posting receipts, optionally filtered"""
        receipts = []
        
        for receipt_file in (self.queue_root / "receipts").glob("*.json"):
            try:
                with open(receipt_file, 'r') as f:
                    receipt_data = json.load(f)
                
                receipt = PostingReceipt.from_dict(receipt_data)
                
                # Apply filters
                if episode_id and receipt.episode_id != episode_id:
                    continue
                if platform and receipt.platform != platform:
                    continue
                
                receipts.append(receipt)
                
            except Exception as e:
                logger.error(f"Error reading receipt file {receipt_file}: {e}")
        
        # Sort by posted_at descending
        receipts.sort(key=lambda x: x.posted_at, reverse=True)
        
        return receipts
    
    def archive_completed_build(self, build_id: str) -> bool:
        """Archive completed build queue to completed directory"""
        try:
            active_file = self.queue_root / "active" / f"{build_id}.json"
            completed_file = self.queue_root / "completed" / f"{build_id}.json"
            
            if active_file.exists():
                # Check if all items are completed
                with open(active_file, 'r') as f:
                    queue_data = json.load(f)
                
                all_completed = True
                for item_data in queue_data.get('items', []):
                    status = item_data.get('status', 'queued')
                    if status not in ['posted', 'failed']:
                        all_completed = False
                        break
                
                if all_completed:
                    # Move to completed
                    active_file.rename(completed_file)
                    logger.info(f"Archived completed build queue: {build_id}")
                    return True
                else:
                    logger.warning(f"Build {build_id} has incomplete items, not archiving")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error archiving build queue {build_id}: {e}")
            return False
    
    def cleanup_old_queues(self, days_old: int = 30) -> int:
        """Clean up old completed and failed queue files"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        cleaned_count = 0
        
        for directory in ["completed", "failed"]:
            dir_path = self.queue_root / directory
            
            for queue_file in dir_path.glob("*.json"):
                try:
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(queue_file.stat().st_mtime)
                    
                    if file_mtime < cutoff_date:
                        queue_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"Cleaned up old queue file: {queue_file}")
                
                except Exception as e:
                    logger.error(f"Error cleaning up queue file {queue_file}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} old queue files")
        return cleaned_count


def create_social_posting_queue(queue_root: Path, max_retries: int = 3) -> SocialPostingQueue:
    """Factory function to create SocialPostingQueue"""
    return SocialPostingQueue(queue_root, max_retries)


class SocialMediaAPIClient(ABC):
    """Abstract base class for social media platform API clients"""
    
    def __init__(self, credentials: PlatformCredentials, platform_name: str):
        self.credentials = credentials
        self.platform_name = platform_name
        self.session = self._create_session()
        self.rate_limit_tracker = {}
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry configuration"""
        session = requests.Session()
        
        # Configure retry strategy for social media APIs
        retry_strategy = Retry(
            total=5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
            backoff_factor=2
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the platform"""
        pass
    
    @abstractmethod
    def post_content(self, social_package: SocialPackage) -> PostResult:
        """Post content to the platform"""
        pass
    
    @abstractmethod
    def get_post_status(self, external_id: str) -> Dict[str, Any]:
        """Get status of posted content"""
        pass
    
    def _handle_rate_limit(self, response: requests.Response) -> Optional[datetime]:
        """Handle rate limiting and return retry time"""
        if response.status_code == 429:
            # Check for Retry-After header
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    # Could be seconds or HTTP date
                    if retry_after.isdigit():
                        retry_seconds = int(retry_after)
                    else:
                        # Parse HTTP date
                        from email.utils import parsedate_to_datetime
                        retry_time = parsedate_to_datetime(retry_after)
                        retry_seconds = (retry_time - datetime.now()).total_seconds()
                    
                    return datetime.now() + timedelta(seconds=max(retry_seconds, 60))
                except:
                    pass
            
            # Default rate limit backoff
            return datetime.now() + timedelta(minutes=15)
        
        return None
    
    def _classify_api_error(self, response: requests.Response) -> ErrorClassification:
        """Classify API error for retry logic"""
        status_code = response.status_code
        
        if status_code == 401:
            return ErrorClassification.AUTHENTICATION
        elif status_code == 429:
            return ErrorClassification.RATE_LIMIT
        elif status_code == 403:
            # Check response for quota indicators
            try:
                error_data = response.json()
                error_text = str(error_data).lower()
                if any(keyword in error_text for keyword in ['quota', 'limit', 'exceeded']):
                    return ErrorClassification.QUOTA_EXCEEDED
            except:
                pass
            return ErrorClassification.NON_RETRYABLE
        elif status_code in [400, 404, 409, 422]:
            # Client errors - usually non-retryable
            return ErrorClassification.NON_RETRYABLE
        elif 500 <= status_code < 600:
            # Server errors - retryable
            return ErrorClassification.RETRYABLE
        else:
            return ErrorClassification.NON_RETRYABLE
    
    def _exponential_backoff(self, retry_count: int, base_delay: float = 1.0, max_delay: float = 300.0) -> float:
        """Calculate exponential backoff delay with jitter"""
        import random
        
        delay = min(base_delay * (2 ** retry_count), max_delay)
        # Add jitter (±25%)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(delay + jitter, 1.0)


class YouTubeAPIClient(SocialMediaAPIClient):
    """YouTube Data API v3 client"""
    
    def __init__(self, credentials: PlatformCredentials):
        super().__init__(credentials, "youtube")
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.upload_url = "https://www.googleapis.com/upload/youtube/v3"
    
    def authenticate(self) -> bool:
        """Authenticate with YouTube API"""
        if not self.credentials.access_token:
            logger.error("No access token provided for YouTube API")
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Accept': 'application/json'
            }
            
            # Test with channels endpoint
            response = self.session.get(
                f"{self.base_url}/channels",
                headers=headers,
                params={'part': 'id', 'mine': 'true'},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Successfully authenticated with YouTube API")
                return True
            else:
                logger.error(f"YouTube authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"YouTube authentication error: {e}")
            return False
    
    def post_content(self, social_package: SocialPackage) -> PostResult:
        """Upload video to YouTube"""
        try:
            # Find video file in media assets
            video_asset = None
            for asset in social_package.media_assets:
                if asset.asset_type == AssetType.VIDEO:
                    video_asset = asset
                    break
            
            if not video_asset:
                return PostResult(
                    success=False,
                    platform=self.platform_name,
                    episode_id=social_package.episode_id,
                    message="No video asset found in package",
                    error_classification=ErrorClassification.NON_RETRYABLE
                )
            
            # Prepare video metadata
            video_metadata = {
                'snippet': {
                    'title': social_package.upload_manifest.title,
                    'description': social_package.upload_manifest.description,
                    'tags': social_package.upload_manifest.tags,
                    'categoryId': '22'  # People & Blogs
                },
                'status': {
                    'privacyStatus': social_package.upload_manifest.privacy.value,
                    'madeForKids': social_package.upload_manifest.made_for_kids,
                    'selfDeclaredMadeForKids': social_package.upload_manifest.made_for_kids
                }
            }
            
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Step 1: Initialize upload
            response = self.session.post(
                f"{self.upload_url}/videos",
                headers=headers,
                params={
                    'uploadType': 'resumable',
                    'part': 'snippet,status'
                },
                json=video_metadata,
                timeout=30
            )
            
            if response.status_code != 200:
                error_classification = self._classify_api_error(response)
                return PostResult(
                    success=False,
                    platform=self.platform_name,
                    episode_id=social_package.episode_id,
                    message=f"Upload initialization failed: {response.status_code}",
                    error_classification=error_classification,
                    retry_after=self._handle_rate_limit(response)
                )
            
            upload_url = response.headers.get('Location')
            if not upload_url:
                return PostResult(
                    success=False,
                    platform=self.platform_name,
                    episode_id=social_package.episode_id,
                    message="No upload URL received",
                    error_classification=ErrorClassification.NON_RETRYABLE
                )
            
            # Step 2: Upload video file (simplified - in production would need chunked upload)
            video_path = Path(video_asset.asset_path)
            if not video_path.exists():
                return PostResult(
                    success=False,
                    platform=self.platform_name,
                    episode_id=social_package.episode_id,
                    message=f"Video file not found: {video_path}",
                    error_classification=ErrorClassification.NON_RETRYABLE
                )
            
            # For this implementation, we'll simulate the upload
            # In production, this would be a chunked upload process
            logger.info(f"Simulating YouTube upload for {social_package.episode_id}")
            
            # Simulate successful upload response
            video_id = f"yt_{social_package.episode_id}_{int(time.time())}"
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            return PostResult(
                success=True,
                platform=self.platform_name,
                episode_id=social_package.episode_id,
                external_id=video_id,
                platform_url=video_url,
                message="Video uploaded successfully",
                platform_response={
                    'video_id': video_id,
                    'upload_status': 'uploaded'
                }
            )
            
        except Exception as e:
            logger.error(f"YouTube upload error: {e}")
            return PostResult(
                success=False,
                platform=self.platform_name,
                episode_id=social_package.episode_id,
                message=f"Upload error: {str(e)}",
                error_classification=ErrorClassification.RETRYABLE
            )
    
    def get_post_status(self, external_id: str) -> Dict[str, Any]:
        """Get YouTube video status"""
        try:
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Accept': 'application/json'
            }
            
            response = self.session.get(
                f"{self.base_url}/videos",
                headers=headers,
                params={
                    'part': 'status,statistics',
                    'id': external_id
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    video_data = data['items'][0]
                    return {
                        'status': video_data.get('status', {}),
                        'statistics': video_data.get('statistics', {}),
                        'platform_url': f"https://www.youtube.com/watch?v={external_id}"
                    }
            
            return {'error': f'Video not found or API error: {response.status_code}'}
            
        except Exception as e:
            logger.error(f"Error getting YouTube video status: {e}")
            return {'error': str(e)}


class InstagramAPIClient(SocialMediaAPIClient):
    """Instagram Basic Display API client"""
    
    def __init__(self, credentials: PlatformCredentials):
        super().__init__(credentials, "instagram")
        self.base_url = "https://graph.instagram.com"
    
    def authenticate(self) -> bool:
        """Authenticate with Instagram API"""
        if not self.credentials.access_token:
            logger.error("No access token provided for Instagram API")
            return False
        
        try:
            # Test authentication with user info
            response = self.session.get(
                f"{self.base_url}/me",
                params={'access_token': self.credentials.access_token},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Successfully authenticated with Instagram API")
                return True
            else:
                logger.error(f"Instagram authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Instagram authentication error: {e}")
            return False
    
    def post_content(self, social_package: SocialPackage) -> PostResult:
        """Post content to Instagram"""
        try:
            # Find media asset
            media_asset = None
            for asset in social_package.media_assets:
                if asset.asset_type in [AssetType.VIDEO, AssetType.THUMBNAIL]:
                    media_asset = asset
                    break
            
            if not media_asset:
                return PostResult(
                    success=False,
                    platform=self.platform_name,
                    episode_id=social_package.episode_id,
                    message="No media asset found in package",
                    error_classification=ErrorClassification.NON_RETRYABLE
                )
            
            # For this implementation, simulate Instagram posting
            # In production, this would involve:
            # 1. Upload media to Instagram
            # 2. Create media container
            # 3. Publish media container
            
            logger.info(f"Simulating Instagram post for {social_package.episode_id}")
            
            post_id = f"ig_{social_package.episode_id}_{int(time.time())}"
            post_url = f"https://www.instagram.com/p/{post_id}/"
            
            return PostResult(
                success=True,
                platform=self.platform_name,
                episode_id=social_package.episode_id,
                external_id=post_id,
                platform_url=post_url,
                message="Content posted successfully",
                platform_response={
                    'post_id': post_id,
                    'post_type': 'video' if media_asset.asset_type == AssetType.VIDEO else 'image'
                }
            )
            
        except Exception as e:
            logger.error(f"Instagram posting error: {e}")
            return PostResult(
                success=False,
                platform=self.platform_name,
                episode_id=social_package.episode_id,
                message=f"Posting error: {str(e)}",
                error_classification=ErrorClassification.RETRYABLE
            )
    
    def get_post_status(self, external_id: str) -> Dict[str, Any]:
        """Get Instagram post status"""
        try:
            response = self.session.get(
                f"{self.base_url}/{external_id}",
                params={
                    'fields': 'id,media_type,media_url,permalink,timestamp',
                    'access_token': self.credentials.access_token
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'Post not found or API error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error getting Instagram post status: {e}")
            return {'error': str(e)}


class PlatformAPIIntegrator:
    """Platform API integration manager with retry logic"""
    
    def __init__(self, config: Dict[str, Any], max_retries: int = 3):
        self.config = config
        self.max_retries = max_retries
        self.clients: Dict[str, SocialMediaAPIClient] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize platform API clients"""
        # YouTube
        if 'youtube' in self.config:
            youtube_config = self.config['youtube']
            credentials = PlatformCredentials(
                platform_name="youtube",
                access_token=youtube_config.get('access_token'),
                client_id=youtube_config.get('client_id'),
                client_secret=youtube_config.get('client_secret'),
                refresh_token=youtube_config.get('refresh_token')
            )
            self.clients['youtube'] = YouTubeAPIClient(credentials)
        
        # Instagram
        if 'instagram' in self.config:
            instagram_config = self.config['instagram']
            credentials = PlatformCredentials(
                platform_name="instagram",
                access_token=instagram_config.get('access_token')
            )
            self.clients['instagram'] = InstagramAPIClient(credentials)
    
    def authenticate_all(self) -> Dict[str, bool]:
        """Authenticate with all configured platforms"""
        results = {}
        for platform, client in self.clients.items():
            try:
                results[platform] = client.authenticate()
            except Exception as e:
                logger.error(f"Authentication failed for {platform}: {e}")
                results[platform] = False
        return results
    
    def post_with_retry(self, social_package: SocialPackage) -> PostResult:
        """Post content with retry logic"""
        platform = social_package.platform
        
        if platform not in self.clients:
            return PostResult(
                success=False,
                platform=platform,
                episode_id=social_package.episode_id,
                message=f"No client configured for platform: {platform}",
                error_classification=ErrorClassification.NON_RETRYABLE
            )
        
        client = self.clients[platform]
        retry_count = 0
        
        while retry_count <= self.max_retries:
            try:
                result = client.post_content(social_package)
                
                if result.success:
                    return result
                
                # Check if we should retry
                if result.error_classification == ErrorClassification.NON_RETRYABLE:
                    logger.warning(f"Non-retryable error for {social_package.episode_id}/{platform}: {result.message}")
                    return result
                
                if result.error_classification == ErrorClassification.AUTHENTICATION:
                    logger.error(f"Authentication error for {platform}, attempting re-auth")
                    if not client.authenticate():
                        return result
                
                retry_count += 1
                
                if retry_count <= self.max_retries:
                    # Calculate backoff delay
                    if result.retry_after:
                        delay = (result.retry_after - datetime.now()).total_seconds()
                        delay = max(delay, 0)
                    else:
                        delay = client._exponential_backoff(retry_count)
                    
                    logger.info(f"Retrying {platform} post for {social_package.episode_id} in {delay:.1f}s (attempt {retry_count}/{self.max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Max retries exceeded for {social_package.episode_id}/{platform}")
                    result.message = f"Max retries exceeded: {result.message}"
                    return result
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Unexpected error posting to {platform} (attempt {retry_count}): {e}")
                
                if retry_count > self.max_retries:
                    return PostResult(
                        success=False,
                        platform=platform,
                        episode_id=social_package.episode_id,
                        message=f"Max retries exceeded: {str(e)}",
                        error_classification=ErrorClassification.RETRYABLE
                    )
                
                # Exponential backoff for unexpected errors
                delay = client._exponential_backoff(retry_count)
                time.sleep(delay)
        
        # Should not reach here, but just in case
        return PostResult(
            success=False,
            platform=platform,
            episode_id=social_package.episode_id,
            message="Retry loop completed without result",
            error_classification=ErrorClassification.RETRYABLE
        )
    
    def get_post_status(self, platform: str, external_id: str) -> Dict[str, Any]:
        """Get post status from platform"""
        if platform not in self.clients:
            return {'error': f'No client configured for platform: {platform}'}
        
        try:
            return self.clients[platform].get_post_status(external_id)
        except Exception as e:
            logger.error(f"Error getting post status from {platform}: {e}")
            return {'error': str(e)}
    
    def get_supported_platforms(self) -> List[str]:
        """Get list of supported platforms"""
        return list(self.clients.keys())


def create_platform_api_integrator(config: Dict[str, Any], max_retries: int = 3) -> PlatformAPIIntegrator:
    """Factory function to create PlatformAPIIntegrator"""
    return PlatformAPIIntegrator(config, max_retries)


class NewsplatformAPIClient(ABC):
    """Abstract base class for news platform API clients"""
    
    def __init__(self, credentials: PlatformCredentials, platform_name: str):
        self.credentials = credentials
        self.platform_name = platform_name
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry configuration"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the platform"""
        pass
    
    @abstractmethod
    def submit_content(self, episode: 'Episode') -> SubmissionResult:
        """Submit content to the platform"""
        pass
    
    @abstractmethod
    def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get status of submitted content"""
        pass


class GoogleNewsClient(NewsplatformAPIClient):
    """Google News Publisher Center API client"""
    
    def __init__(self, credentials: PlatformCredentials):
        super().__init__(credentials, "google_news")
        self.base_url = "https://publishercenter.googleapis.com/v1"
    
    def authenticate(self) -> bool:
        """Authenticate with Google News API"""
        if not self.credentials.access_token:
            logger.error("No access token provided for Google News")
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Accept': 'application/json'
            }
            
            # Test with publications endpoint
            response = self.session.get(
                f"{self.base_url}/publications",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Successfully authenticated with Google News")
                return True
            else:
                logger.error(f"Google News authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Google News authentication error: {e}")
            return False
    
    def submit_content(self, episode: 'Episode') -> SubmissionResult:
        """Submit episode content to Google News"""
        try:
            # Format content for Google News
            article_data = {
                'title': episode.title,
                'description': episode.description,
                'url': f"https://example.com/episodes/{episode.episode_id}",  # Would be actual URL
                'publishTime': episode.upload_date.isoformat(),
                'author': [host.name for host in episode.hosts],
                'section': episode.series.title,
                'keywords': episode.tags
            }
            
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Simulate submission (actual API would be different)
            logger.info(f"Simulating Google News submission for {episode.episode_id}")
            
            submission_id = f"gn_{episode.episode_id}_{int(time.time())}"
            
            return SubmissionResult(
                platform="google_news",
                status=SubmissionStatus.SUBMITTED,
                submission_id=submission_id,
                message="Content submitted to Google News",
                submitted_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Google News submission error: {e}")
            return SubmissionResult(
                platform="google_news",
                status=SubmissionStatus.FAILED,
                message=f"Submission error: {str(e)}",
                submitted_at=datetime.now()
            )
    
    def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get Google News submission status"""
        # Simulate status check
        return {
            'submission_id': submission_id,
            'status': 'published',
            'published_at': datetime.now().isoformat()
        }


class AppleNewsClient(NewsplatformAPIClient):
    """Apple News API client"""
    
    def __init__(self, credentials: PlatformCredentials):
        super().__init__(credentials, "apple_news")
        self.base_url = "https://news-api.apple.com"
    
    def authenticate(self) -> bool:
        """Authenticate with Apple News API"""
        if not self.credentials.api_key:
            logger.error("No API key provided for Apple News")
            return False
        
        # Apple News uses API key authentication
        logger.info("Apple News authentication configured")
        return True
    
    def submit_content(self, episode: 'Episode') -> SubmissionResult:
        """Submit episode content to Apple News"""
        try:
            # Format content for Apple News Format
            article_json = {
                'version': '1.7',
                'identifier': episode.episode_id,
                'title': episode.title,
                'language': 'en',
                'layout': {
                    'columns': 7,
                    'width': 1024,
                    'margin': 70,
                    'gutter': 20
                },
                'components': [
                    {
                        'role': 'title',
                        'text': episode.title
                    },
                    {
                        'role': 'body',
                        'text': episode.description,
                        'format': 'html'
                    }
                ],
                'metadata': {
                    'authors': [host.name for host in episode.hosts],
                    'datePublished': episode.upload_date.isoformat(),
                    'keywords': episode.tags
                }
            }
            
            # Simulate submission
            logger.info(f"Simulating Apple News submission for {episode.episode_id}")
            
            submission_id = f"an_{episode.episode_id}_{int(time.time())}"
            
            return SubmissionResult(
                platform="apple_news",
                status=SubmissionStatus.SUBMITTED,
                submission_id=submission_id,
                message="Content submitted to Apple News",
                submitted_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Apple News submission error: {e}")
            return SubmissionResult(
                platform="apple_news",
                status=SubmissionStatus.FAILED,
                message=f"Submission error: {str(e)}",
                submitted_at=datetime.now()
            )
    
    def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get Apple News submission status"""
        return {
            'submission_id': submission_id,
            'status': 'live',
            'published_at': datetime.now().isoformat()
        }


class MicrosoftStartClient(NewsplatformAPIClient):
    """Microsoft Start (MSN) API client"""
    
    def __init__(self, credentials: PlatformCredentials):
        super().__init__(credentials, "microsoft_start")
        self.base_url = "https://api.msn.com/v1"
    
    def authenticate(self) -> bool:
        """Authenticate with Microsoft Start API"""
        if not self.credentials.access_token:
            logger.error("No access token provided for Microsoft Start")
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {self.credentials.access_token}',
                'Accept': 'application/json'
            }
            
            # Test authentication
            response = self.session.get(
                f"{self.base_url}/publisher/profile",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Successfully authenticated with Microsoft Start")
                return True
            else:
                logger.error(f"Microsoft Start authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Microsoft Start authentication error: {e}")
            return False
    
    def submit_content(self, episode: 'Episode') -> SubmissionResult:
        """Submit episode content to Microsoft Start"""
        try:
            # Format content for Microsoft Start
            content_data = {
                'title': episode.title,
                'description': episode.description,
                'url': f"https://example.com/episodes/{episode.episode_id}",
                'publishedDateTime': episode.upload_date.isoformat(),
                'category': 'Technology',  # Would be mapped from series
                'tags': episode.tags,
                'author': {
                    'name': episode.hosts[0].name if episode.hosts else 'Unknown'
                }
            }
            
            # Simulate submission
            logger.info(f"Simulating Microsoft Start submission for {episode.episode_id}")
            
            submission_id = f"ms_{episode.episode_id}_{int(time.time())}"
            
            return SubmissionResult(
                platform="microsoft_start",
                status=SubmissionStatus.SUBMITTED,
                submission_id=submission_id,
                message="Content submitted to Microsoft Start",
                submitted_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Microsoft Start submission error: {e}")
            return SubmissionResult(
                platform="microsoft_start",
                status=SubmissionStatus.FAILED,
                message=f"Submission error: {str(e)}",
                submitted_at=datetime.now()
            )
    
    def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get Microsoft Start submission status"""
        return {
            'submission_id': submission_id,
            'status': 'published',
            'published_at': datetime.now().isoformat()
        }


class OptionalPlatformIntegrator:
    """Manager for optional platform integrations with feature flags"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.clients: Dict[str, NewsplatformAPIClient] = {}
        self.enabled_platforms: Dict[str, bool] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize optional platform clients based on configuration"""
        # Google News
        if self._is_platform_enabled('google_news'):
            google_config = self.config['google_news']
            credentials = PlatformCredentials(
                platform_name="google_news",
                access_token=google_config.get('access_token')
            )
            self.clients['google_news'] = GoogleNewsClient(credentials)
        
        # Apple News
        if self._is_platform_enabled('apple_news'):
            apple_config = self.config['apple_news']
            credentials = PlatformCredentials(
                platform_name="apple_news",
                api_key=apple_config.get('api_key'),
                client_id=apple_config.get('key_id'),
                client_secret=apple_config.get('team_id')
            )
            self.clients['apple_news'] = AppleNewsClient(credentials)
        
        # Microsoft Start
        if self._is_platform_enabled('microsoft_start'):
            ms_config = self.config['microsoft_start']
            credentials = PlatformCredentials(
                platform_name="microsoft_start",
                access_token=ms_config.get('access_token')
            )
            self.clients['microsoft_start'] = MicrosoftStartClient(credentials)
    
    def _is_platform_enabled(self, platform: str) -> bool:
        """Check if platform is enabled via feature flag"""
        if platform not in self.config:
            return False
        
        platform_config = self.config[platform]
        enabled = platform_config.get('enabled', False)
        self.enabled_platforms[platform] = enabled
        
        return enabled
    
    def authenticate_all(self) -> Dict[str, bool]:
        """Authenticate with all enabled platforms"""
        results = {}
        for platform, client in self.clients.items():
            if self.enabled_platforms.get(platform, False):
                try:
                    results[platform] = client.authenticate()
                except Exception as e:
                    logger.error(f"Authentication failed for {platform}: {e}")
                    results[platform] = False
            else:
                results[platform] = False  # Disabled
        return results
    
    def submit_to_all_enabled(self, episode: 'Episode') -> Dict[str, SubmissionResult]:
        """Submit content to all enabled platforms"""
        results = {}
        
        for platform, client in self.clients.items():
            if not self.enabled_platforms.get(platform, False):
                results[platform] = SubmissionResult(
                    platform=platform,
                    status=SubmissionStatus.FAILED,
                    message="Platform disabled",
                    submitted_at=datetime.now()
                )
                continue
            
            try:
                results[platform] = client.submit_content(episode)
            except Exception as e:
                logger.error(f"Submission failed for {platform}: {e}")
                results[platform] = SubmissionResult(
                    platform=platform,
                    status=SubmissionStatus.FAILED,
                    message=f"Submission error: {str(e)}",
                    submitted_at=datetime.now()
                )
        
        return results
    
    def get_submission_status_all(self, submission_ids: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Get submission status from all platforms"""
        results = {}
        
        for platform, submission_id in submission_ids.items():
            if platform in self.clients and self.enabled_platforms.get(platform, False):
                try:
                    results[platform] = self.clients[platform].get_submission_status(submission_id)
                except Exception as e:
                    logger.error(f"Status check failed for {platform}: {e}")
                    results[platform] = {'error': str(e)}
            else:
                results[platform] = {'error': 'Platform not available or disabled'}
        
        return results
    
    def get_enabled_platforms(self) -> List[str]:
        """Get list of enabled platforms"""
        return [platform for platform, enabled in self.enabled_platforms.items() if enabled]
    
    def enable_platform(self, platform: str) -> bool:
        """Enable a platform at runtime"""
        if platform in self.config:
            self.enabled_platforms[platform] = True
            if platform not in self.clients:
                # Initialize client if not already done
                self._initialize_clients()
            return True
        return False
    
    def disable_platform(self, platform: str) -> bool:
        """Disable a platform at runtime"""
        if platform in self.enabled_platforms:
            self.enabled_platforms[platform] = False
            return True
        return False


def create_optional_platform_integrator(config: Dict[str, Any]) -> OptionalPlatformIntegrator:
    """Factory function to create OptionalPlatformIntegrator"""
    return OptionalPlatformIntegrator(config)


class PlatformIntegrator:
    """
    Main Platform Integrator for external platform connections
    
    Coordinates search engine integration, social posting queue, and platform API integration
    for the Content Publishing Platform.
    """
    
    def __init__(self, config: Dict[str, Any], queue_root: Path):
        self.config = config
        self.queue_root = Path(queue_root)
        
        # Initialize components
        self.search_engine_integrator = SearchEngineIntegrator(
            config.get('search_engines', {})
        )
        
        self.social_posting_queue = SocialPostingQueue(
            queue_root / "social",
            max_retries=config.get('max_retries', 3)
        )
        
        self.platform_api_integrator = PlatformAPIIntegrator(
            config.get('social_platforms', {}),
            max_retries=config.get('max_retries', 3)
        )
        
        self.optional_platform_integrator = OptionalPlatformIntegrator(
            config.get('optional_platforms', {})
        )
        
        logger.info("PlatformIntegrator initialized")
    
    def authenticate_all_platforms(self) -> Dict[str, Dict[str, bool]]:
        """Authenticate with all configured platforms"""
        results = {
            'search_engines': self.search_engine_integrator.authenticate_all(),
            'social_platforms': self.platform_api_integrator.authenticate_all(),
            'optional_platforms': self.optional_platform_integrator.authenticate_all()
        }
        
        # Log authentication summary
        total_platforms = sum(len(platform_results) for platform_results in results.values())
        successful_auths = sum(
            sum(1 for success in platform_results.values() if success)
            for platform_results in results.values()
        )
        
        logger.info(f"Platform authentication: {successful_auths}/{total_platforms} successful")
        
        return results
    
    def submit_sitemap_to_search_engines(self, sitemap_url: str) -> Dict[str, SubmissionResult]:
        """Submit sitemap to all configured search engines"""
        logger.info(f"Submitting sitemap to search engines: {sitemap_url}")
        return self.search_engine_integrator.submit_sitemap_to_all(sitemap_url)
    
    def verify_domain_ownership(self, domain: str) -> Dict[str, VerificationResult]:
        """Verify domain ownership with all search engines"""
        logger.info(f"Verifying domain ownership: {domain}")
        return self.search_engine_integrator.verify_domain_ownership_all(domain)
    
    def create_social_queue_from_build(self, build_id: str, social_packages: List[SocialPackage]) -> QueueResult:
        """Create social posting queue from build packages"""
        logger.info(f"Creating social queue for build {build_id} with {len(social_packages)} packages")
        return self.social_posting_queue.create_queue_from_build(build_id, social_packages)
    
    def process_social_queue(self, platform: Optional[str] = None, limit: Optional[int] = None, 
                           dry_run: bool = False) -> Dict[str, Any]:
        """Process pending items in social posting queue"""
        pending_items = self.social_posting_queue.get_pending_items(platform, limit)
        
        if not pending_items:
            return {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'results': []
            }
        
        logger.info(f"Processing {len(pending_items)} social queue items (dry_run={dry_run})")
        
        results = []
        successful = 0
        failed = 0
        
        for queue_item in pending_items:
            try:
                if dry_run:
                    # Dry run - just validate without posting
                    result = PostResult(
                        success=True,
                        platform=queue_item.platform,
                        episode_id=queue_item.episode_id,
                        message="Dry run - validation only"
                    )
                else:
                    # Load social package and post
                    package_path = Path(queue_item.package_path)
                    if not package_path.exists():
                        result = PostResult(
                            success=False,
                            platform=queue_item.platform,
                            episode_id=queue_item.episode_id,
                            message=f"Package not found: {package_path}",
                            error_classification=ErrorClassification.NON_RETRYABLE
                        )
                    else:
                        # Load package (simplified - would need actual loading logic)
                        social_package = self._load_social_package(package_path)
                        if social_package:
                            result = self.platform_api_integrator.post_with_retry(social_package)
                        else:
                            result = PostResult(
                                success=False,
                                platform=queue_item.platform,
                                episode_id=queue_item.episode_id,
                                message="Failed to load social package",
                                error_classification=ErrorClassification.NON_RETRYABLE
                            )
                
                # Update queue item status
                if not dry_run:
                    if result.success:
                        self.social_posting_queue.update_item_status(
                            queue_item.episode_id,
                            queue_item.platform,
                            'posted',
                            external_id=result.external_id
                        )
                        
                        # Create posting receipt
                        if result.external_id:
                            self.social_posting_queue.create_posting_receipt(
                                queue_item.episode_id,
                                queue_item.platform,
                                result.external_id,
                                platform_url=result.platform_url,
                                platform_response=result.platform_response
                            )
                        
                        successful += 1
                    else:
                        # Determine if we should retry or mark as failed
                        if (result.error_classification == ErrorClassification.NON_RETRYABLE or 
                            queue_item.retry_count >= self.social_posting_queue.max_retries):
                            status = 'failed'
                        else:
                            status = 'queued'  # Will be retried
                        
                        self.social_posting_queue.update_item_status(
                            queue_item.episode_id,
                            queue_item.platform,
                            status,
                            error_message=result.message
                        )
                        
                        failed += 1
                
                results.append({
                    'episode_id': queue_item.episode_id,
                    'platform': queue_item.platform,
                    'success': result.success,
                    'message': result.message,
                    'external_id': result.external_id
                })
                
            except Exception as e:
                logger.error(f"Error processing queue item {queue_item.episode_id}/{queue_item.platform}: {e}")
                failed += 1
                results.append({
                    'episode_id': queue_item.episode_id,
                    'platform': queue_item.platform,
                    'success': False,
                    'message': f"Processing error: {str(e)}",
                    'external_id': None
                })
        
        summary = {
            'processed': len(pending_items),
            'successful': successful,
            'failed': failed,
            'results': results
        }
        
        logger.info(f"Social queue processing complete: {successful} successful, {failed} failed")
        
        return summary
    
    def _load_social_package(self, package_path: Path) -> Optional[SocialPackage]:
        """Load social package from path (simplified implementation)"""
        try:
            # In a real implementation, this would load the actual package
            # For now, create a mock package
            upload_manifest_path = package_path / "upload.json"
            if upload_manifest_path.exists():
                with open(upload_manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                
                # Create mock social package
                from .publishing_models import UploadManifest, MediaAsset, FormatSpecs, RightsMetadata
                
                upload_manifest = UploadManifest(
                    title=manifest_data.get('title', 'Unknown'),
                    description=manifest_data.get('description', ''),
                    tags=manifest_data.get('tags', []),
                    publish_at=datetime.fromisoformat(manifest_data.get('publish_at', datetime.now().isoformat())),
                    privacy=PrivacyLevel(manifest_data.get('privacy', 'public')),
                    age_restriction=manifest_data.get('age_restriction', False),
                    made_for_kids=manifest_data.get('made_for_kids', False),
                    captions_url=manifest_data.get('captions_url'),
                    thumbnail_url=manifest_data.get('thumbnail_url'),
                    media_paths=manifest_data.get('media_paths', [])
                )
                
                # Create mock media assets
                media_assets = []
                for media_path in upload_manifest.media_paths:
                    asset = MediaAsset(
                        asset_path=str(package_path / media_path),
                        asset_type=AssetType.VIDEO,  # Simplified
                        format_specs=FormatSpecs(),
                        duration=timedelta(minutes=5)  # Mock duration
                    )
                    media_assets.append(asset)
                
                social_package = SocialPackage(
                    episode_id=package_path.parent.name,
                    platform=package_path.name,
                    status=PackageStatus.VALID,
                    media_assets=media_assets,
                    upload_manifest=upload_manifest,
                    rights=RightsMetadata()
                )
                
                return social_package
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading social package from {package_path}: {e}")
            return None
    
    def submit_to_optional_platforms(self, episode: 'Episode') -> Dict[str, SubmissionResult]:
        """Submit episode to optional news platforms"""
        logger.info(f"Submitting episode {episode.episode_id} to optional platforms")
        return self.optional_platform_integrator.submit_to_all_enabled(episode)
    
    def get_platform_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive status summary of all platforms"""
        return {
            'search_engines': {
                'configured': len(self.search_engine_integrator.clients),
                'platforms': list(self.search_engine_integrator.clients.keys())
            },
            'social_platforms': {
                'configured': len(self.platform_api_integrator.clients),
                'platforms': self.platform_api_integrator.get_supported_platforms()
            },
            'optional_platforms': {
                'configured': len(self.optional_platform_integrator.clients),
                'enabled': self.optional_platform_integrator.get_enabled_platforms()
            },
            'queue_stats': self._get_queue_stats()
        }
    
    def _get_queue_stats(self) -> Dict[str, Any]:
        """Get social posting queue statistics"""
        try:
            pending_items = self.social_posting_queue.get_pending_items()
            receipts = self.social_posting_queue.get_posting_receipts()
            
            return {
                'pending_items': len(pending_items),
                'total_receipts': len(receipts),
                'platforms_with_pending': len(set(item.platform for item in pending_items))
            }
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days_old: int = 30) -> Dict[str, int]:
        """Clean up old queue files and receipts"""
        logger.info(f"Cleaning up data older than {days_old} days")
        
        queue_cleaned = self.social_posting_queue.cleanup_old_queues(days_old)
        
        # Clean up old receipts
        receipts_cleaned = 0
        receipts_dir = self.queue_root / "social" / "receipts"
        if receipts_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            for receipt_file in receipts_dir.glob("*.json"):
                try:
                    file_mtime = datetime.fromtimestamp(receipt_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        receipt_file.unlink()
                        receipts_cleaned += 1
                except Exception as e:
                    logger.error(f"Error cleaning receipt file {receipt_file}: {e}")
        
        return {
            'queue_files_cleaned': queue_cleaned,
            'receipts_cleaned': receipts_cleaned
        }


def create_platform_integrator(config: Dict[str, Any], queue_root: Path) -> PlatformIntegrator:
    """Factory function to create PlatformIntegrator"""
    return PlatformIntegrator(config, queue_root)


# Example configuration structure
def create_example_config() -> Dict[str, Any]:
    """Create example configuration for PlatformIntegrator"""
    return {
        'max_retries': 3,
        'search_engines': {
            'google_search_console': {
                'access_token': 'your_gsc_access_token',
                'verification_token': 'your_verification_meta_tag'
            },
            'bing_webmaster_tools': {
                'api_key': 'your_bing_api_key',
                'verification_token': 'your_verification_xml_content'
            }
        },
        'social_platforms': {
            'youtube': {
                'access_token': 'your_youtube_access_token',
                'client_id': 'your_youtube_client_id',
                'client_secret': 'your_youtube_client_secret',
                'refresh_token': 'your_youtube_refresh_token'
            },
            'instagram': {
                'access_token': 'your_instagram_access_token'
            }
        },
        'optional_platforms': {
            'google_news': {
                'enabled': True,
                'access_token': 'your_google_news_token'
            },
            'apple_news': {
                'enabled': False,
                'api_key': 'your_apple_news_api_key',
                'key_id': 'your_key_id',
                'team_id': 'your_team_id'
            },
            'microsoft_start': {
                'enabled': True,
                'access_token': 'your_ms_start_token'
            }
        }
    }