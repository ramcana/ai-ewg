# Content Publishing Platform - Dry Run Setup Checklist

This checklist provides step-by-step instructions for setting up the environment and conducting a comprehensive dry run test of the Content Publishing Platform.

## Prerequisites Setup

### 1. Python Environment

- [ ] **Python 3.8+** installed
- [ ] **Virtual environment** created and activated
  ```bash
  python -m venv venv
  source venv/bin/activate  # Linux/Mac
  # or
  venv\Scripts\activate     # Windows
  ```
- [ ] **Required Python packages** installed
  ```bash
  pip install pyyaml requests python-dateutil pathlib dataclasses
  pip install lxml beautifulsoup4  # For HTML/XML processing
  pip install psutil  # For system monitoring
  ```

### 2. Directory Structure Setup

- [ ] **Create base directories**
  ```bash
  mkdir -p data/{staging,public,backups,social,meta,transcripts}
  mkdir -p config/environments
  mkdir -p logs
  mkdir -p temp
  ```

## Configuration Setup

### 3. Basic Configuration Files

- [ ] **Run configuration setup**
  ```bash
  python -c "from src.core.publishing_config import setup_default_config_files; setup_default_config_files('config')"
  ```
- [ ] **Verify config files created**
  - [ ] `config/publishing.yaml`
  - [ ] `config/integrations.yaml`
  - [ ] `config/environments/development.yaml`
  - [ ] `config/environments/staging.yaml`
  - [ ] `config/environments/production.yaml`

### 4. Environment Variables (Optional for Dry Run)

Create `.env` file in project root:

```bash
# Basic settings
PUBLISHING_ENVIRONMENT=development
PUBLISHING_BASE_URL=http://localhost:3000

# Database (optional for dry run)
PUBLISHING_DATABASE_URL=sqlite:///data/publishing.db

# Logging
PUBLISHING_LOG_LEVEL=INFO
PUBLISHING_LOG_DIRECTORY=logs
```

## External Service Setup (For Full Integration Testing)

### 5. Google Services Setup

- [ ] **Google Search Console API**

  - [ ] Create Google Cloud Project
  - [ ] Enable Search Console API
  - [ ] Create service account credentials
  - [ ] Download JSON key file → `config/google_search_console_key.json`
  - [ ] Set environment variable: `PUBLISHING_GOOGLE_SEARCH_CONSOLE_KEY=path/to/key.json`

- [ ] **Google Analytics (Optional)**
  - [ ] Create GA4 property
  - [ ] Get tracking ID
  - [ ] Set environment variable: `PUBLISHING_GOOGLE_ANALYTICS_KEY=GA4-XXXXXXXXX`

### 6. Bing Webmaster Tools Setup

- [ ] **Bing Webmaster Tools API**
  - [ ] Register at Bing Webmaster Tools
  - [ ] Get API key
  - [ ] Set environment variable: `PUBLISHING_BING_WEBMASTER_KEY=your_api_key`

### 7. Social Media Platform Setup

- [ ] **YouTube API (Optional)**

  - [ ] Enable YouTube Data API v3
  - [ ] Create OAuth 2.0 credentials
  - [ ] Set environment variables:
    ```bash
    PUBLISHING_YOUTUBE_API_KEY=your_api_key
    PUBLISHING_YOUTUBE_CLIENT_SECRET=your_client_secret
    ```

- [ ] **Instagram Basic Display API (Optional)**
  - [ ] Create Facebook App
  - [ ] Enable Instagram Basic Display
  - [ ] Set environment variables:
    ```bash
    PUBLISHING_INSTAGRAM_API_KEY=your_app_id
    PUBLISHING_INSTAGRAM_CLIENT_SECRET=your_app_secret
    ```

### 8. CDN Setup (Optional)

- [ ] **Cloudflare (Recommended)**
  - [ ] Create Cloudflare account
  - [ ] Add domain to Cloudflare
  - [ ] Get API token with Zone:Edit permissions
  - [ ] Set environment variables:
    ```bash
    PUBLISHING_CLOUDFLARE_API_KEY=your_api_token
    PUBLISHING_CLOUDFLARE_ZONE_ID=your_zone_id
    ```

## Test Data Setup

### 9. Sample Content Creation

- [ ] **Create sample manifest**

  ```bash
  python examples/complete_publishing_workflow.py
  ```

  This will create `data/publish_manifest.json`

- [ ] **Create sample media files (Optional)**

  ```bash
  mkdir -p data/media
  # Add sample video files, thumbnails, transcripts
  ```

- [ ] **Verify manifest structure**
  - [ ] Episodes array with sample data
  - [ ] Series array with sample data
  - [ ] Hosts array with sample data
  - [ ] Paths configuration

### 10. Configuration Validation

- [ ] **Update config files for your environment**

  Edit `config/environments/development.yaml`:

  ```yaml
  name: development
  base_url: "http://localhost:3000"
  content_base_path: "data"
  cdn_enabled: false
  max_concurrent_workers: 2
  batch_size: 10
  feature_overrides:
    platform_integration: false # Disable for dry run
    analytics_tracking: false # Disable for dry run
    social_generation: true # Enable for testing
  ```

- [ ] **Update integrations config**

  Edit `config/integrations.yaml`:

  ```yaml
  # Enable only what you have credentials for
  google_search_console_enabled: false # Set to true if you have credentials
  bing_webmaster_tools_enabled: false # Set to true if you have credentials
  youtube_enabled: false # Set to true if you have credentials
  instagram_enabled: false # Set to true if you have credentials

  # Keep these disabled for dry run
  google_analytics_enabled: false
  cloudflare_enabled: false
  ```

## Dry Run Test Execution

### 11. System Validation

- [ ] **Run system validation**
  ```bash
  python -c "
  from src.core.main_integration import create_content_publishing_platform
  platform = create_content_publishing_platform('config', auto_setup=True)
  result = platform.validate_system()
  print(f'Validation: {\"PASSED\" if result.is_valid else \"FAILED\"}')
  print(f'Errors: {len(result.errors)}')
  print(f'Warnings: {len(result.warnings)}')
  for error in result.errors[:5]:
      print(f'  - {error.message}')
  "
  ```

### 12. Component Testing

- [ ] **Test content registry**

  ```bash
  python -c "
  from src.core.content_registry import ContentRegistry
  registry = ContentRegistry('data')
  try:
      manifest = registry.load_manifest('data/publish_manifest.json')
      print(f'Manifest loaded: {manifest.build_id}')
      episodes = registry.get_episodes()
      print(f'Episodes found: {len(episodes)}')
  except Exception as e:
      print(f'Error: {e}')
  "
  ```

- [ ] **Test web generator**
  ```bash
  python -c "
  from src.core.web_generator import WebGenerator
  from src.core.content_registry import ContentRegistry
  registry = ContentRegistry('data')
  generator = WebGenerator()
  try:
      manifest = registry.load_manifest('data/publish_manifest.json')
      episodes = registry.get_episodes()
      if episodes:
          page = generator.generate_episode_page(episodes[0])
          print(f'Generated page title: {page.title}')
          print(f'Page content length: {len(page.content)} chars')
  except Exception as e:
      print(f'Error: {e}')
  "
  ```

### 13. Full Workflow Dry Run

- [ ] **Execute complete workflow example**

  ```bash
  python examples/complete_publishing_workflow.py
  ```

- [ ] **Verify output**
  - [ ] No critical errors in console output
  - [ ] Configuration validation passes
  - [ ] System health check passes
  - [ ] Content analysis completes
  - [ ] Workflow simulation runs successfully

### 14. Advanced Testing (If External Services Configured)

- [ ] **Test with real manifest**

  ```bash
  python -c "
  from src.core.main_integration import create_content_publishing_platform
  platform = create_content_publishing_platform('config')

  # Add progress callback
  def progress(msg, pct, meta):
      print(f'[{pct*100:5.1f}%] {msg}')

  platform.add_progress_callback(progress)

  # Execute workflow (will use dry run mode if external services not configured)
  report = platform.publish_content('data/publish_manifest.json')
  print(f'Workflow status: {report.workflow_result.status.value}')
  print(f'Pages generated: {report.metrics.pages_generated}')
  "
  ```

## Troubleshooting Checklist

### 15. Common Issues

- [ ] **Import errors**

  - Check Python path includes `src` directory
  - Verify all required packages installed
  - Check for circular imports

- [ ] **Configuration errors**

  - Verify YAML syntax in config files
  - Check file permissions
  - Validate environment variable names

- [ ] **Missing directories**

  - Ensure all required directories exist
  - Check write permissions
  - Verify path separators for your OS

- [ ] **API credential issues**
  - Verify API keys are valid
  - Check API quotas and limits
  - Ensure proper permissions/scopes

### 16. Validation Commands

- [ ] **Check system health**

  ```bash
  python -c "
  from src.core.main_integration import create_content_publishing_platform
  platform = create_content_publishing_platform('config')
  status = platform.get_system_status()
  print('System Status:')
  for key, value in status.items():
      print(f'  {key}: {value}')
  "
  ```

- [ ] **Test individual components**

  ```bash
  # Test configuration manager
  python -c "
  from src.core.publishing_config import create_configuration_manager
  config = create_configuration_manager('config')
  validation = config.validate_configuration()
  print(f'Config valid: {validation.is_valid}')
  "

  # Test publishing system
  python -c "
  from src.core.publishing_system import create_publishing_system
  system = create_publishing_system()
  health = system.get_system_health()
  print(f'System health: {health[\"overall_status\"]}')
  "
  ```

## Success Criteria

### 17. Dry Run Success Indicators

- [ ] **All configuration files created successfully**
- [ ] **System validation passes with no critical errors**
- [ ] **Sample manifest loads without errors**
- [ ] **Content registry can process sample data**
- [ ] **Web generator creates HTML pages**
- [ ] **Feed generator creates RSS/XML feeds**
- [ ] **Social generator creates packages (if enabled)**
- [ ] **Workflow orchestrator completes simulation**
- [ ] **No unhandled exceptions during execution**
- [ ] **Log files created with appropriate messages**

### 18. Optional Success Indicators (With External Services)

- [ ] **Google Search Console API connection successful**
- [ ] **Bing Webmaster Tools API connection successful**
- [ ] **Social media API connections successful**
- [ ] **CDN API connection successful**
- [ ] **Sitemap submission test successful**
- [ ] **Social media posting test successful**

## Next Steps After Successful Dry Run

### 19. Production Preparation

- [ ] **Review and update production configuration**
- [ ] **Set up production environment variables**
- [ ] **Configure production database**
- [ ] **Set up production CDN**
- [ ] **Configure production monitoring**
- [ ] **Set up backup procedures**
- [ ] **Create deployment scripts**
- [ ] **Document operational procedures**

### 20. Monitoring Setup

- [ ] **Configure log aggregation**
- [ ] **Set up performance monitoring**
- [ ] **Configure alerting**
- [ ] **Set up health checks**
- [ ] **Create dashboards**

---

## Quick Start Commands

For a minimal dry run test:

```bash
# 1. Setup
python -c "from src.core.publishing_config import setup_default_config_files; setup_default_config_files('config')"

# 2. Create directories
mkdir -p data/{staging,public,backups,social,meta,transcripts} config/environments logs temp

# 3. Run example
python examples/complete_publishing_workflow.py

# 4. Validate
python -c "
from src.core.main_integration import create_content_publishing_platform
platform = create_content_publishing_platform('config', auto_setup=True)
result = platform.validate_system()
print(f'System Ready: {result.is_valid}')
"
```

This should get you up and running for basic testing without external service dependencies.
