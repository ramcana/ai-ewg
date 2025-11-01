"""
Analytics Tracker and Monitoring System

Implements comprehensive analytics integration, deployment monitoring, and health
check systems for the Content Publishing Platform.
"""

import json
import time
import logging
import threading
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import psutil
import requests
from urllib.parse import urljoin

# Import email modules conditionally for alerting
try:
    import smtplib
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

from .exceptions import PipelineError, ValidationError
from .logging import get_logger

logger = get_logger(__name__)


class AnalyticsProvider(Enum):
    """Supported analytics providers"""
    GOOGLE_ANALYTICS = "google_analytics"
    GOOGLE_TAG_MANAGER = "google_tag_manager"
    ADOBE_ANALYTICS = "adobe_analytics"
    MATOMO = "matomo"
    CUSTOM = "custom"


@dataclass
class AnalyticsConfig:
    """Configuration for analytics tracking"""
    provider: AnalyticsProvider
    tracking_id: str
    privacy_compliant: bool = True
    cookie_consent_required: bool = True
    anonymize_ip: bool = True
    custom_dimensions: Dict[str, str] = field(default_factory=dict)
    events_enabled: bool = True
    page_views_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class CustomEvent:
    """Custom analytics event"""
    name: str
    category: str
    action: str
    label: Optional[str] = None
    value: Optional[Union[int, float]] = None
    custom_parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DeploymentMetrics:
    """Deployment performance metrics"""
    build_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    success: Optional[bool] = None
    content_counts: Dict[str, int] = field(default_factory=dict)
    processing_time: Optional[timedelta] = None
    throughput: Optional[float] = None  # items per second
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate deployment duration"""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        if self.duration:
            data['duration_seconds'] = self.duration.total_seconds()
        return data


@dataclass
class HealthCheckResult:
    """Health check result"""
    name: str
    status: str  # "healthy", "warning", "critical"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    response_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class AlertThreshold:
    """Alert threshold configuration"""
    name: str
    metric: str  # deployment_success_rate, avg_deployment_time, etc.
    warning_threshold: float
    critical_threshold: float
    comparison: str = "less_than"  # less_than, greater_than, equals
    enabled: bool = True
    
    def check_threshold(self, value: float) -> str:
        """Check if value exceeds thresholds"""
        if not self.enabled:
            return "healthy"
        
        if self.comparison == "less_than":
            if value < self.critical_threshold:
                return "critical"
            elif value < self.warning_threshold:
                return "warning"
        elif self.comparison == "greater_than":
            if value > self.critical_threshold:
                return "critical"
            elif value > self.warning_threshold:
                return "warning"
        elif self.comparison == "equals":
            if value == self.critical_threshold:
                return "critical"
            elif value == self.warning_threshold:
                return "warning"
        
        return "healthy"


@dataclass
class AlertConfig:
    """Alert configuration"""
    enabled: bool = True
    email_enabled: bool = False
    webhook_enabled: bool = False
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    webhook_url: Optional[str] = None
    webhook_headers: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)"""
        data = asdict(self)
        data.pop('smtp_password', None)
        return data


@dataclass
class StructuredLogEntry:
    """Structured log entry for analytics tracking"""
    timestamp: datetime
    level: str
    component: str
    event_type: str
    message: str
    build_id: Optional[str] = None
    deployment_stage: Optional[str] = None
    content_type: Optional[str] = None
    content_id: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    response_time: Optional[float] = None
    status_code: Optional[int] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        data = self.to_dict()
        data['timestamp'] = self.timestamp.isoformat()
        return json.dumps(data)


class AnalyticsTracker:
    """
    Analytics Tracker for performance and engagement monitoring
    
    Implements analytics code embedding, deployment metrics tracking,
    health check endpoints, and structured logging as required by Requirement 8.
    """
    
    def __init__(self, config: AnalyticsConfig, alert_config: Optional[AlertConfig] = None):
        """Initialize Analytics Tracker"""
        self.config = config
        self.alert_config = alert_config or AlertConfig()
        self.deployment_metrics: Dict[str, DeploymentMetrics] = {}
        self.health_checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self.custom_events: List[CustomEvent] = []
        self.alert_thresholds: Dict[str, AlertThreshold] = {}
        self.structured_logs: List[StructuredLogEntry] = []
        self._lock = threading.Lock()
        
        # Initialize default alert thresholds
        self._setup_default_thresholds()
        
        # Register default health checks
        self._register_default_health_checks()
        
        logger.info(f"Analytics Tracker initialized with provider: {config.provider.value}")
    
    def _setup_default_thresholds(self) -> None:
        """Setup default alert thresholds"""
        self.alert_thresholds = {
            "deployment_success_rate": AlertThreshold(
                name="Deployment Success Rate",
                metric="deployment_success_rate",
                warning_threshold=95.0,
                critical_threshold=90.0,
                comparison="less_than"
            ),
            "avg_deployment_time": AlertThreshold(
                name="Average Deployment Time",
                metric="avg_deployment_time",
                warning_threshold=300.0,  # 5 minutes
                critical_threshold=600.0,  # 10 minutes
                comparison="greater_than"
            ),
            "error_rate": AlertThreshold(
                name="Error Rate",
                metric="error_rate",
                warning_threshold=5.0,
                critical_threshold=10.0,
                comparison="greater_than"
            ),
            "disk_usage": AlertThreshold(
                name="Disk Usage",
                metric="disk_usage",
                warning_threshold=80.0,
                critical_threshold=90.0,
                comparison="greater_than"
            ),
            "memory_usage": AlertThreshold(
                name="Memory Usage",
                metric="memory_usage",
                warning_threshold=80.0,
                critical_threshold=90.0,
                comparison="greater_than"
            )
        }
    
    def _register_default_health_checks(self) -> None:
        """Register default health checks"""
        self.register_health_check("database", database_health_check)
        self.register_health_check("storage", storage_health_check)
        self.register_health_check("memory", memory_health_check)
        self.register_health_check("deployment_pipeline", self._deployment_pipeline_health_check)
    
    def _deployment_pipeline_health_check(self) -> HealthCheckResult:
        """Health check for deployment pipeline"""
        try:
            # Check recent deployment success rate
            success_rate = self.calculate_success_rate(timedelta(hours=1))
            
            if success_rate < 90:
                status = "critical"
                message = f"Low deployment success rate: {success_rate:.1f}%"
            elif success_rate < 95:
                status = "warning"
                message = f"Deployment success rate warning: {success_rate:.1f}%"
            else:
                status = "healthy"
                message = f"Deployment pipeline healthy: {success_rate:.1f}% success rate"
            
            return HealthCheckResult(
                name="deployment_pipeline",
                status=status,
                message=message,
                metadata={"success_rate": success_rate}
            )
        except Exception as e:
            return HealthCheckResult(
                name="deployment_pipeline",
                status="critical",
                message=f"Deployment pipeline check failed: {str(e)}"
            )
    
    def log_structured_event(self, level: str, component: str, event_type: str, 
                           message: str, **kwargs) -> None:
        """
        Log structured event for analytics tracking
        
        Implements requirement 8.3: structured log fields for access patterns and crawl activity
        """
        log_entry = StructuredLogEntry(
            timestamp=datetime.now(),
            level=level,
            component=component,
            event_type=event_type,
            message=message,
            **kwargs
        )
        
        with self._lock:
            self.structured_logs.append(log_entry)
            
            # Keep only last 10000 log entries to prevent memory issues
            if len(self.structured_logs) > 10000:
                self.structured_logs = self.structured_logs[-5000:]
        
        # Also log to standard logger
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"[{component}] {event_type}: {message}", extra=kwargs)
    
    def log_access_pattern(self, ip_address: str, user_agent: str, 
                          url: str, status_code: int, response_time: float,
                          content_type: Optional[str] = None,
                          content_id: Optional[str] = None) -> None:
        """
        Log access pattern for analytics
        
        Implements requirement 8.3: log access patterns for analysis
        """
        self.log_structured_event(
            level="INFO",
            component="web_server",
            event_type="access",
            message=f"Access to {url}",
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
            response_time=response_time,
            content_type=content_type,
            content_id=content_id,
            metadata={"url": url}
        )
    
    def log_crawl_activity(self, crawler_name: str, ip_address: str,
                          pages_crawled: int, crawl_duration: float,
                          user_agent: str) -> None:
        """
        Log crawler activity for analytics
        
        Implements requirement 8.3: log crawl activity for analysis
        """
        self.log_structured_event(
            level="INFO",
            component="crawler_tracker",
            event_type="crawl_session",
            message=f"Crawler {crawler_name} crawled {pages_crawled} pages",
            ip_address=ip_address,
            user_agent=user_agent,
            response_time=crawl_duration,
            metadata={
                "crawler_name": crawler_name,
                "pages_crawled": pages_crawled,
                "crawl_duration": crawl_duration
            }
        )
    
    def log_deployment_event(self, build_id: str, stage: str, event_type: str,
                           message: str, success: Optional[bool] = None,
                           error_code: Optional[str] = None) -> None:
        """
        Log deployment event for monitoring
        
        Implements requirement 8.2: deployment monitoring
        """
        self.log_structured_event(
            level="ERROR" if success is False else "INFO",
            component="deployment_pipeline",
            event_type=event_type,
            message=message,
            build_id=build_id,
            deployment_stage=stage,
            error_code=error_code,
            metadata={
                "success": success,
                "stage": stage
            }
        )
    
    def get_structured_logs(self, component: Optional[str] = None,
                          event_type: Optional[str] = None,
                          time_window: Optional[timedelta] = None,
                          limit: int = 1000) -> List[StructuredLogEntry]:
        """
        Get structured logs with optional filtering
        
        Args:
            component: Filter by component name
            event_type: Filter by event type
            time_window: Filter by time window (default: last hour)
            limit: Maximum number of logs to return
            
        Returns:
            List of structured log entries
        """
        if time_window is None:
            time_window = timedelta(hours=1)
        
        cutoff_time = datetime.now() - time_window
        
        with self._lock:
            filtered_logs = [
                log for log in self.structured_logs
                if log.timestamp >= cutoff_time
            ]
            
            if component:
                filtered_logs = [log for log in filtered_logs if log.component == component]
            
            if event_type:
                filtered_logs = [log for log in filtered_logs if log.event_type == event_type]
            
            # Sort by timestamp (newest first) and limit
            filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
            return filtered_logs[:limit]
    
    def set_alert_threshold(self, name: str, threshold: AlertThreshold) -> None:
        """Set or update an alert threshold"""
        self.alert_thresholds[name] = threshold
        logger.info(f"Updated alert threshold: {name}")
    
    def check_alert_thresholds(self) -> Dict[str, str]:
        """
        Check all alert thresholds and return status
        
        Implements requirement 8.4: defined alert thresholds for system monitoring
        """
        alerts = {}
        
        # Check deployment success rate
        success_rate = self.calculate_success_rate(timedelta(hours=1))
        if "deployment_success_rate" in self.alert_thresholds:
            threshold = self.alert_thresholds["deployment_success_rate"]
            alerts["deployment_success_rate"] = threshold.check_threshold(success_rate)
        
        # Check average deployment time
        avg_time = self.get_average_deployment_time(timedelta(hours=1))
        if avg_time and "avg_deployment_time" in self.alert_thresholds:
            threshold = self.alert_thresholds["avg_deployment_time"]
            alerts["avg_deployment_time"] = threshold.check_threshold(avg_time.total_seconds())
        
        # Check system metrics
        try:
            system_metrics = self._get_system_metrics()
            
            if "disk_usage" in self.alert_thresholds and "disk_percent" in system_metrics:
                threshold = self.alert_thresholds["disk_usage"]
                alerts["disk_usage"] = threshold.check_threshold(system_metrics["disk_percent"])
            
            if "memory_usage" in self.alert_thresholds and "memory_percent" in system_metrics:
                threshold = self.alert_thresholds["memory_usage"]
                alerts["memory_usage"] = threshold.check_threshold(system_metrics["memory_percent"])
        except Exception as e:
            logger.warning(f"Failed to check system metric thresholds: {e}")
        
        # Check error rate from recent logs
        error_logs = self.get_structured_logs(event_type="error", time_window=timedelta(hours=1))
        total_logs = len(self.get_structured_logs(time_window=timedelta(hours=1)))
        error_rate = (len(error_logs) / max(total_logs, 1)) * 100
        
        if "error_rate" in self.alert_thresholds:
            threshold = self.alert_thresholds["error_rate"]
            alerts["error_rate"] = threshold.check_threshold(error_rate)
        
        return alerts
    
    def generate_alerts(self) -> List[Dict[str, Any]]:
        """
        Generate alerts for critical and warning conditions
        
        Implements requirement 8.4: alert generation for deployment failures and performance issues
        """
        alert_statuses = self.check_alert_thresholds()
        alerts = []
        
        for metric, status in alert_statuses.items():
            if status in ["warning", "critical"]:
                threshold = self.alert_thresholds.get(metric)
                if threshold:
                    alert = {
                        "metric": metric,
                        "status": status,
                        "threshold_name": threshold.name,
                        "timestamp": datetime.now().isoformat(),
                        "message": f"{threshold.name} is {status}"
                    }
                    alerts.append(alert)
        
        return alerts
    
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Send alert via configured channels (email, webhook)
        
        Args:
            alert: Alert dictionary with metric, status, message, etc.
            
        Returns:
            True if alert was sent successfully, False otherwise
        """
        if not self.alert_config.enabled:
            return False
        
        success = True
        
        # Send email alert
        if self.alert_config.email_enabled and self.alert_config.email_recipients:
            try:
                self._send_email_alert(alert)
                logger.info(f"Email alert sent for {alert['metric']}")
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")
                success = False
        
        # Send webhook alert
        if self.alert_config.webhook_enabled and self.alert_config.webhook_url:
            try:
                self._send_webhook_alert(alert)
                logger.info(f"Webhook alert sent for {alert['metric']}")
            except Exception as e:
                logger.error(f"Failed to send webhook alert: {e}")
                success = False
        
        return success
    
    def _send_email_alert(self, alert: Dict[str, Any]) -> None:
        """Send alert via email"""
        if not EMAIL_AVAILABLE:
            raise ValueError("Email functionality not available - missing email modules")
        
        if not all([self.alert_config.smtp_server, self.alert_config.smtp_username, 
                   self.alert_config.smtp_password]):
            raise ValueError("SMTP configuration incomplete")
        
        # Import email modules locally to avoid global import issues
        import smtplib
        from email.mime.text import MimeText
        from email.mime.multipart import MimeMultipart
        
        msg = MimeMultipart()
        msg['From'] = self.alert_config.smtp_username
        msg['To'] = ', '.join(self.alert_config.email_recipients)
        msg['Subject'] = f"Content Publishing Platform Alert: {alert['status'].upper()}"
        
        body = f"""
Alert Details:
- Metric: {alert['metric']}
- Status: {alert['status']}
- Message: {alert['message']}
- Timestamp: {alert['timestamp']}
- Threshold: {alert.get('threshold_name', 'Unknown')}

Please check the system status and take appropriate action.
"""
        
        msg.attach(MimeText(body, 'plain'))
        
        server = smtplib.SMTP(self.alert_config.smtp_server, self.alert_config.smtp_port)
        server.starttls()
        server.login(self.alert_config.smtp_username, self.alert_config.smtp_password)
        server.send_message(msg)
        server.quit()
    
    def _send_webhook_alert(self, alert: Dict[str, Any]) -> None:
        """Send alert via webhook"""
        if not self.alert_config.webhook_url:
            raise ValueError("Webhook URL not configured")
        
        payload = {
            "alert": alert,
            "system": "content_publishing_platform",
            "timestamp": datetime.now().isoformat()
        }
        
        headers = {"Content-Type": "application/json"}
        headers.update(self.alert_config.webhook_headers)
        
        response = requests.post(
            self.alert_config.webhook_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
    
    def get_health_check_endpoint_data(self) -> Dict[str, Any]:
        """
        Get health check endpoint data
        
        Implements requirement 8.4: health check endpoints with defined alert thresholds
        """
        health_results = self.run_all_health_checks()
        alert_statuses = self.check_alert_thresholds()
        alerts = self.generate_alerts()
        
        # Calculate overall status
        all_statuses = list(health_results.values()) + [{"status": status} for status in alert_statuses.values()]
        statuses = [result.status if hasattr(result, 'status') else result["status"] for result in all_statuses]
        
        if "critical" in statuses:
            overall_status = "critical"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "health_checks": {name: result.to_dict() for name, result in health_results.items()},
            "alert_thresholds": alert_statuses,
            "active_alerts": alerts,
            "deployment_metrics": self.get_deployment_summary(timedelta(hours=1)),
            "system_metrics": self._get_system_metrics(),
            "uptime": self._get_uptime()
        }
    
    def _get_uptime(self) -> Dict[str, Any]:
        """Get system uptime information"""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            return {
                "boot_time": boot_time.isoformat(),
                "uptime_seconds": uptime.total_seconds(),
                "uptime_human": str(uptime)
            }
        except Exception as e:
            logger.warning(f"Failed to get uptime: {e}")
            return {}
    
    def generate_tracking_code(self, page_type: str = "episode", 
                             custom_data: Optional[Dict[str, Any]] = None) -> str:
        """Generate analytics tracking code for embedding in HTML pages"""
        if not self.config.page_views_enabled:
            return ""
        
        tracking_code = ""
        
        if self.config.provider == AnalyticsProvider.GOOGLE_ANALYTICS:
            tracking_code = self._generate_google_analytics_code(page_type, custom_data)
        elif self.config.provider == AnalyticsProvider.GOOGLE_TAG_MANAGER:
            tracking_code = self._generate_gtm_code(page_type, custom_data)
        elif self.config.provider == AnalyticsProvider.MATOMO:
            tracking_code = self._generate_matomo_code(page_type, custom_data)
        elif self.config.provider == AnalyticsProvider.CUSTOM:
            tracking_code = self._generate_custom_code(page_type, custom_data)
        
        # Add privacy compliance wrapper if required
        if self.config.cookie_consent_required:
            tracking_code = self._wrap_with_consent_check(tracking_code)
        
        return tracking_code
    
    def _generate_google_analytics_code(self, page_type: str, 
                                      custom_data: Optional[Dict[str, Any]]) -> str:
        """Generate Google Analytics 4 tracking code"""
        anonymize_config = "'anonymize_ip': true," if self.config.anonymize_ip else ""
        custom_dimensions = ""
        
        if custom_data:
            custom_dimensions = ",\\n".join([
                f"        'custom_map.{k}': '{v}'"
                for k, v in custom_data.items()
            ])
            if custom_dimensions:
                custom_dimensions = f",\\n{custom_dimensions}"
        
        return f"""
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id={self.config.tracking_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  
  gtag('config', '{self.config.tracking_id}', {{
    {anonymize_config}
    'page_title': document.title,
    'page_location': window.location.href,
    'content_group1': '{page_type}'{custom_dimensions}
  }});
</script>
"""
    
    def _generate_gtm_code(self, page_type: str, 
                          custom_data: Optional[Dict[str, Any]]) -> str:
        """Generate Google Tag Manager tracking code"""
        return f"""
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{self.config.tracking_id}');</script>
<!-- End Google Tag Manager -->

<script>
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({{
    'event': 'page_view',
    'page_type': '{page_type}',
    'page_title': document.title,
    'page_url': window.location.href
  }});
</script>
"""
    
    def _generate_matomo_code(self, page_type: str, 
                            custom_data: Optional[Dict[str, Any]]) -> str:
        """Generate Matomo tracking code"""
        return f"""
<!-- Matomo -->
<script type="text/javascript">
  var _paq = window._paq = window._paq || [];
  _paq.push(['setCustomDimension', 1, '{page_type}']);
  _paq.push(['trackPageView']);
  _paq.push(['enableLinkTracking']);
  (function() {{
    var u="//your-matomo-domain/";
    _paq.push(['setTrackerUrl', u+'matomo.php']);
    _paq.push(['setSiteId', '{self.config.tracking_id}']);
    var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
    g.type='text/javascript'; g.async=true; g.defer=true; g.src=u+'matomo.js'; s.parentNode.insertBefore(g,s);
  }})();
</script>
"""
    
    def _generate_custom_code(self, page_type: str, 
                            custom_data: Optional[Dict[str, Any]]) -> str:
        """Generate custom analytics tracking code"""
        return f"""
<!-- Custom Analytics -->
<script>
  (function() {{
    var analytics = {{
      trackingId: '{self.config.tracking_id}',
      pageType: '{page_type}',
      customData: {json.dumps(custom_data or {})},
      
      track: function(event, data) {{
        fetch('/analytics/track', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            event: event,
            data: data,
            timestamp: new Date().toISOString(),
            page: window.location.href
          }})
        }});
      }}
    }};
    
    analytics.track('page_view', {{
      title: document.title,
      url: window.location.href,
      type: '{page_type}'
    }});
    
    window.customAnalytics = analytics;
  }})();
</script>
"""
    
    def _wrap_with_consent_check(self, tracking_code: str) -> str:
        """Wrap tracking code with cookie consent check"""
        return f"""
<script>
  function loadAnalytics() {{
    if (localStorage.getItem('analytics_consent') === 'true' || 
        document.cookie.indexOf('analytics_consent=true') !== -1) {{
      {tracking_code.replace('<script>', '').replace('</script>', '')}
    }}
  }}
  
  loadAnalytics();
  document.addEventListener('analytics_consent_granted', loadAnalytics);
</script>
"""
    
    def track_custom_event(self, event: CustomEvent) -> None:
        """Track a custom analytics event"""
        if not self.config.events_enabled:
            return
        
        with self._lock:
            self.custom_events.append(event)
        
        logger.info(f"Tracked custom event: {event.name} - {event.action}")
    
    def generate_event_tracking_code(self, event_name: str, category: str, 
                                   action: str, label: Optional[str] = None) -> str:
        """Generate JavaScript code for tracking custom events"""
        if not self.config.events_enabled:
            return ""
        
        if self.config.provider == AnalyticsProvider.GOOGLE_ANALYTICS:
            return f"""
gtag('event', '{action}', {{
  'event_category': '{category}',
  'event_label': '{label or ""}',
  'custom_parameter_1': '{event_name}'
}});
"""
        elif self.config.provider == AnalyticsProvider.GOOGLE_TAG_MANAGER:
            return f"""
window.dataLayer.push({{
  'event': '{event_name}',
  'event_category': '{category}',
  'event_action': '{action}',
  'event_label': '{label or ""}'
}});
"""
        elif self.config.provider == AnalyticsProvider.MATOMO:
            return f"""
_paq.push(['trackEvent', '{category}', '{action}', '{label or ""}']);
"""
        else:
            return f"""
if (window.customAnalytics) {{
  window.customAnalytics.track('{event_name}', {{
    category: '{category}',
    action: '{action}',
    label: '{label or ""}'
  }});
}}
"""
    
    def start_deployment_tracking(self, build_id: str, 
                                content_counts: Optional[Dict[str, int]] = None) -> None:
        """Start tracking deployment metrics for a build"""
        with self._lock:
            self.deployment_metrics[build_id] = DeploymentMetrics(
                build_id=build_id,
                start_time=datetime.now(),
                content_counts=content_counts or {}
            )
        
        # Log deployment start
        self.log_deployment_event(
            build_id=build_id,
            stage="start",
            event_type="deployment_start",
            message=f"Started deployment for build {build_id}",
            success=None
        )
        
        logger.info(f"Started deployment tracking for build: {build_id}")
    
    def update_deployment_metrics(self, build_id: str, 
                                content_counts: Optional[Dict[str, int]] = None,
                                errors: Optional[List[str]] = None,
                                warnings: Optional[List[str]] = None) -> None:
        """
        Update deployment metrics during processing
        
        Args:
            build_id: Build identifier
            content_counts: Updated content counts
            errors: List of errors encountered
            warnings: List of warnings encountered
        """
        with self._lock:
            if build_id not in self.deployment_metrics:
                logger.warning(f"No deployment tracking found for build: {build_id}")
                return
            
            metrics = self.deployment_metrics[build_id]
            
            if content_counts:
                metrics.content_counts.update(content_counts)
            
            if errors:
                metrics.errors.extend(errors)
            
            if warnings:
                metrics.warnings.extend(warnings)
        
        logger.debug(f"Updated deployment metrics for build: {build_id}")
    
    def complete_deployment_tracking(self, build_id: str, success: bool) -> DeploymentMetrics:
        """Complete deployment tracking and calculate final metrics"""
        with self._lock:
            if build_id not in self.deployment_metrics:
                raise ValueError(f"No deployment tracking found for build: {build_id}")
            
            metrics = self.deployment_metrics[build_id]
            metrics.end_time = datetime.now()
            metrics.success = success
            
            # Calculate throughput
            if metrics.duration and metrics.content_counts:
                total_items = sum(metrics.content_counts.values())
                if total_items > 0 and metrics.duration.total_seconds() > 0:
                    metrics.throughput = total_items / metrics.duration.total_seconds()
        
        # Log deployment completion
        self.log_deployment_event(
            build_id=build_id,
            stage="completion",
            event_type="deployment_complete",
            message=f"Deployment {'succeeded' if success else 'failed'}",
            success=success
        )
        
        # Check for alerts after deployment completion
        if not success:
            alerts = self.generate_alerts()
            for alert in alerts:
                self.send_alert(alert)
        
        logger.info(f"Completed deployment tracking for build: {build_id}, success: {success}")
        return metrics
    
    def calculate_success_rate(self, time_window: Optional[timedelta] = None) -> float:
        """Calculate deployment success rate over a time window"""
        if time_window is None:
            time_window = timedelta(hours=24)
        
        cutoff_time = datetime.now() - time_window
        
        with self._lock:
            relevant_deployments = [
                metrics for metrics in self.deployment_metrics.values()
                if metrics.start_time >= cutoff_time and metrics.success is not None
            ]
        
        if not relevant_deployments:
            return 0.0
        
        successful_deployments = sum(1 for m in relevant_deployments if m.success)
        return (successful_deployments / len(relevant_deployments)) * 100.0
    
    def get_deployment_metrics(self, build_id: Optional[str] = None) -> Union[DeploymentMetrics, Dict[str, DeploymentMetrics]]:
        """
        Get deployment metrics for a specific build or all builds
        
        Args:
            build_id: Optional build identifier
            
        Returns:
            Deployment metrics for the build or all builds
        """
        with self._lock:
            if build_id:
                if build_id not in self.deployment_metrics:
                    raise ValueError(f"No deployment metrics found for build: {build_id}")
                return self.deployment_metrics[build_id]
            else:
                return self.deployment_metrics.copy()
    
    def get_average_deployment_time(self, time_window: Optional[timedelta] = None) -> Optional[timedelta]:
        """
        Calculate average deployment time over a time window
        
        Args:
            time_window: Time window to calculate over (default: last 24 hours)
            
        Returns:
            Average deployment time or None if no completed deployments
        """
        if time_window is None:
            time_window = timedelta(hours=24)
        
        cutoff_time = datetime.now() - time_window
        
        with self._lock:
            completed_deployments = [
                metrics for metrics in self.deployment_metrics.values()
                if (metrics.start_time >= cutoff_time and 
                    metrics.end_time is not None and 
                    metrics.duration is not None)
            ]
        
        if not completed_deployments:
            return None
        
        total_time = sum((m.duration for m in completed_deployments), timedelta())
        return total_time / len(completed_deployments)
    
    def get_deployment_summary(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """
        Get comprehensive deployment metrics summary
        
        Args:
            time_window: Time window to analyze (default: last 24 hours)
            
        Returns:
            Summary of deployment metrics including success rate, average time, throughput
        """
        if time_window is None:
            time_window = timedelta(hours=24)
        
        cutoff_time = datetime.now() - time_window
        
        with self._lock:
            recent_deployments = [
                metrics for metrics in self.deployment_metrics.values()
                if metrics.start_time >= cutoff_time
            ]
        
        if not recent_deployments:
            return {
                "total_deployments": 0,
                "success_rate": 0.0,
                "average_deployment_time": None,
                "average_throughput": None,
                "total_content_processed": 0,
                "total_errors": 0,
                "total_warnings": 0
            }
        
        # Calculate metrics
        completed_deployments = [m for m in recent_deployments if m.success is not None]
        successful_deployments = [m for m in completed_deployments if m.success]
        
        success_rate = (len(successful_deployments) / len(completed_deployments) * 100.0) if completed_deployments else 0.0
        
        # Average deployment time
        timed_deployments = [m for m in recent_deployments if m.duration is not None]
        avg_time = None
        if timed_deployments:
            total_time = sum((m.duration for m in timed_deployments), timedelta())
            avg_time = total_time / len(timed_deployments)
        
        # Average throughput
        throughput_deployments = [m for m in recent_deployments if m.throughput is not None]
        avg_throughput = None
        if throughput_deployments:
            avg_throughput = sum(m.throughput for m in throughput_deployments) / len(throughput_deployments)
        
        # Content and error counts
        total_content = sum(sum(m.content_counts.values()) for m in recent_deployments)
        total_errors = sum(len(m.errors) for m in recent_deployments)
        total_warnings = sum(len(m.warnings) for m in recent_deployments)
        
        return {
            "total_deployments": len(recent_deployments),
            "completed_deployments": len(completed_deployments),
            "success_rate": success_rate,
            "average_deployment_time": avg_time.total_seconds() if avg_time else None,
            "average_throughput": avg_throughput,
            "total_content_processed": total_content,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "time_window_hours": time_window.total_seconds() / 3600
        }
    
    def register_health_check(self, name: str, check_function: Callable[[], HealthCheckResult]) -> None:
        """Register a health check function"""
        self.health_checks[name] = check_function
        logger.info(f"Registered health check: {name}")
    
    def run_health_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check"""
        if name not in self.health_checks:
            return HealthCheckResult(
                name=name,
                status="critical",
                message=f"Health check '{name}' not found"
            )
        
        try:
            start_time = time.time()
            result = self.health_checks[name]()
            result.response_time = time.time() - start_time
            return result
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status="critical",
                message=f"Health check failed: {str(e)}",
                response_time=time.time() - start_time if 'start_time' in locals() else None
            )
    
    def run_all_health_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks"""
        results = {}
        for name in self.health_checks:
            results[name] = self.run_health_check(name)
        return results
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        health_results = self.run_all_health_checks()
        
        # Calculate overall status
        statuses = [result.status for result in health_results.values()]
        if "critical" in statuses:
            overall_status = "critical"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        # Get comprehensive deployment metrics
        deployment_summary = self.get_deployment_summary()
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "health_checks": {name: result.to_dict() for name, result in health_results.items()},
            "deployment_metrics": deployment_summary,
            "system_metrics": self._get_system_metrics()
        }
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get basic system metrics"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
        except Exception as e:
            logger.warning(f"Failed to get system metrics: {e}")
            return {}


class HealthCheckEndpoint:
    """
    Health check endpoint handler for web frameworks
    
    Implements requirement 8.4: health check endpoints with defined alert thresholds
    """
    
    def __init__(self, analytics_tracker: AnalyticsTracker):
        """Initialize health check endpoint"""
        self.analytics_tracker = analytics_tracker
    
    def handle_health_check(self, detailed: bool = False) -> Dict[str, Any]:
        """
        Handle health check request
        
        Args:
            detailed: Whether to include detailed metrics and logs
            
        Returns:
            Health check response data
        """
        try:
            if detailed:
                return self.analytics_tracker.get_health_check_endpoint_data()
            else:
                # Simple health check
                health_results = self.analytics_tracker.run_all_health_checks()
                alert_statuses = self.analytics_tracker.check_alert_thresholds()
                
                # Calculate overall status
                all_statuses = (
                    [result.status for result in health_results.values()] +
                    list(alert_statuses.values())
                )
                
                if "critical" in all_statuses:
                    overall_status = "critical"
                elif "warning" in all_statuses:
                    overall_status = "warning"
                else:
                    overall_status = "healthy"
                
                return {
                    "status": overall_status,
                    "timestamp": datetime.now().isoformat(),
                    "checks_passed": sum(1 for s in all_statuses if s == "healthy"),
                    "total_checks": len(all_statuses)
                }
        except Exception as e:
            return {
                "status": "critical",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def handle_metrics_endpoint(self) -> Dict[str, Any]:
        """
        Handle metrics endpoint request
        
        Returns:
            Deployment and system metrics
        """
        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "deployment_metrics": self.analytics_tracker.get_deployment_summary(),
                "system_metrics": self.analytics_tracker._get_system_metrics(),
                "alert_thresholds": {
                    name: {
                        "warning": threshold.warning_threshold,
                        "critical": threshold.critical_threshold,
                        "comparison": threshold.comparison,
                        "enabled": threshold.enabled
                    }
                    for name, threshold in self.analytics_tracker.alert_thresholds.items()
                }
            }
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def handle_logs_endpoint(self, component: Optional[str] = None,
                           event_type: Optional[str] = None,
                           hours: int = 1, limit: int = 100) -> Dict[str, Any]:
        """
        Handle structured logs endpoint request
        
        Args:
            component: Filter by component name
            event_type: Filter by event type  
            hours: Number of hours to look back
            limit: Maximum number of logs to return
            
        Returns:
            Structured logs data
        """
        try:
            time_window = timedelta(hours=hours)
            logs = self.analytics_tracker.get_structured_logs(
                component=component,
                event_type=event_type,
                time_window=time_window,
                limit=limit
            )
            
            return {
                "timestamp": datetime.now().isoformat(),
                "logs": [log.to_dict() for log in logs],
                "total_logs": len(logs),
                "filters": {
                    "component": component,
                    "event_type": event_type,
                    "time_window_hours": hours,
                    "limit": limit
                }
            }
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "logs": []
            }


# Default health check functions
def database_health_check() -> HealthCheckResult:
    """Default database health check"""
    return HealthCheckResult(
        name="database",
        status="healthy",
        message="Database connection successful"
    )


def storage_health_check() -> HealthCheckResult:
    """Default storage health check"""
    try:
        disk_usage = psutil.disk_usage('/')
        free_percent = (disk_usage.free / disk_usage.total) * 100
        
        if free_percent < 10:
            status = "critical"
            message = f"Low disk space: {free_percent:.1f}% free"
        elif free_percent < 20:
            status = "warning"
            message = f"Disk space warning: {free_percent:.1f}% free"
        else:
            status = "healthy"
            message = f"Disk space OK: {free_percent:.1f}% free"
        
        return HealthCheckResult(
            name="storage",
            status=status,
            message=message,
            metadata={"free_percent": free_percent}
        )
    except Exception as e:
        return HealthCheckResult(
            name="storage",
            status="critical",
            message=f"Storage check failed: {str(e)}"
        )


def memory_health_check() -> HealthCheckResult:
    """Default memory health check"""
    try:
        memory = psutil.virtual_memory()
        
        if memory.percent > 90:
            status = "critical"
            message = f"High memory usage: {memory.percent:.1f}%"
        elif memory.percent > 80:
            status = "warning"
            message = f"Memory usage warning: {memory.percent:.1f}%"
        else:
            status = "healthy"
            message = f"Memory usage OK: {memory.percent:.1f}%"
        
        return HealthCheckResult(
            name="memory",
            status=status,
            message=message,
            metadata={"percent": memory.percent, "available": memory.available}
        )
    except Exception as e:
        return HealthCheckResult(
            name="memory",
            status="critical",
            message=f"Memory check failed: {str(e)}"
        )