"""
Rendering Stage Processor

Generates AI-enhanced web-ready artifacts using WebArtifactGenerator:
- HTML episode page with AI enrichment
- JSON metadata
- Copies transcripts to public assets

Creates: data/public/...
"""

from pathlib import Path
from typing import Dict, Any
import json
import shutil
from datetime import datetime

from ..core.logging import get_logger
from ..core.exceptions import ProcessingError
from ..core.models import EpisodeObject
from ..core.config import PipelineConfig, ConfigurationManager
from ..core.web_artifacts import WebArtifactGenerator

logger = get_logger('pipeline.rendering_stage')


class RenderingStageProcessor:
    """Processes rendering stage - generates AI-enhanced web-ready content"""
    
    def __init__(self, output_dir: str = "data/public", config_path: str = None):
        self.output_dir = Path(output_dir)
        self.shows_dir = self.output_dir / "shows"
        self.assets_dir = self.output_dir / "assets" / "transcripts"
        self.meta_dir = self.output_dir / "meta"
        
        # Create output directories
        self.shows_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize WebArtifactGenerator for AI-enhanced HTML
        try:
            if config_path:
                config_manager = ConfigurationManager(config_path)
                self.config = config_manager.load_config()
            else:
                # Use default config
                config_manager = ConfigurationManager()
                self.config = config_manager.load_config()
        except Exception as e:
            logger.warning(f"Could not load config, using defaults: {e}")
            self.config = None
        
        # Initialize web artifact generator
        # Note: WebArtifactGenerator expects specific config structure
        # For now, pass a minimal config dict
        web_config = {
            'output': {'web_artifacts': str(self.shows_dir.parent)},
            'web': {}
        }
        try:
            self.web_generator = WebArtifactGenerator(web_config)
        except Exception as e:
            logger.warning(f"WebArtifactGenerator initialization failed: {e}")
            self.web_generator = None
    
    async def process(self, episode: EpisodeObject, transcript_data: Dict[str, Any], enrichment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate AI-enhanced web-ready artifacts
        
        Args:
            episode: Episode object
            transcript_data: Transcript data
            enrichment_data: Enrichment data with AI analysis
            
        Returns:
            Dict with paths to generated files
        """
        try:
            logger.info("Starting rendering with AI enrichment", episode_id=episode.episode_id)
            
            # Load enrichment data and attach to episode
            enrichment_json = enrichment_data.get('enrichment_data', {})
            
            # Attach enrichment data to episode object
            # The enrichment should be a dict with ai_analysis section
            episode.enrichment = enrichment_json
            
            logger.info(
                "Enrichment data loaded",
                episode_id=episode.episode_id,
                ai_enhanced=enrichment_json.get('ai_enhanced', False),
                has_ai_analysis='ai_analysis' in enrichment_json
            )
            
            # Create episode directory
            show_slug = episode.metadata.show_slug
            episode_dir = self.shows_dir / show_slug / episode.episode_id
            episode_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy transcripts to assets
            # Build paths from episode_id if not in transcript_data
            if 'txt_path' in transcript_data:
                txt_src = Path(transcript_data['txt_path'])
                vtt_src = Path(transcript_data['vtt_path'])
            else:
                # Fallback to standard paths
                txt_src = Path(f"data/transcripts/txt/{episode.episode_id}.txt")
                vtt_src = Path(f"data/transcripts/vtt/{episode.episode_id}.vtt")
            
            txt_dest = self.assets_dir / f"{episode.episode_id}.txt"
            vtt_dest = self.assets_dir / f"{episode.episode_id}.vtt"
            
            shutil.copy2(txt_src, txt_dest)
            shutil.copy2(vtt_src, vtt_dest)
            
            logger.info("Transcripts copied to assets")
            
            # Generate episode metadata JSON
            meta_path = self.meta_dir / f"{episode.episode_id}.json"
            episode_meta = {
                'episode_id': episode.episode_id,
                'metadata': episode.metadata.to_dict(),
                'media': episode.media.to_dict(),
                'transcripts': {
                    'text': f"/assets/transcripts/{episode.episode_id}.txt",
                    'vtt': f"/assets/transcripts/{episode.episode_id}.vtt"
                },
                'enrichment': enrichment_json,
                'generated_at': datetime.now().isoformat()
            }
            
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(episode_meta, f, indent=2, ensure_ascii=False)
            
            logger.info("Episode metadata JSON created", path=str(meta_path))
            
            # Generate HTML page with AI enhancements
            html_path = episode_dir / "index.html"
            
            # Try using WebArtifactGenerator for AI-enhanced HTML
            if self.web_generator:
                try:
                    logger.info("Using WebArtifactGenerator for AI-enhanced HTML")
                    # WebArtifactGenerator generates HTML directly
                    html_content = self.web_generator._generate_html_content(episode)
                except Exception as e:
                    logger.warning(f"WebArtifactGenerator failed, falling back to simple HTML: {e}")
                    html_content = self._generate_html(episode, transcript_data, enrichment_data)
            else:
                logger.info("Using fallback HTML generation")
                html_content = self._generate_html(episode, transcript_data, enrichment_data)
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info("HTML page generated", path=str(html_path))
            
            return {
                'html_path': str(html_path),
                'meta_path': str(meta_path),
                'transcript_txt': str(txt_dest),
                'transcript_vtt': str(vtt_dest),
                'success': True
            }
            
        except Exception as e:
            logger.error("Rendering failed",
                        episode_id=episode.episode_id,
                        error=str(e))
            raise ProcessingError(f"Rendering stage failed: {e}")
    
    def _generate_html(self, episode: EpisodeObject, transcript_data: Dict[str, Any], enrichment_data: Dict[str, Any]) -> str:
        """Generate HTML page for episode"""
        
        # Get enrichment summary
        summary_data = enrichment_data.get('enrichment_data', {}).get('summary', {})
        key_takeaway = summary_data.get('key_takeaway', '')
        description = summary_data.get('description', episode.metadata.description or '')
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{episode.metadata.title} | {episode.metadata.show_name}</title>
    <meta name="description" content="{description}">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .show-name {{
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        h1 {{
            margin: 10px 0;
            color: #333;
        }}
        .date {{
            color: #999;
            font-size: 14px;
        }}
        .key-takeaway {{
            background: #fff9e6;
            border-left: 4px solid #ffc107;
            padding: 15px 20px;
            margin: 20px 0;
            font-weight: 500;
        }}
        .description {{
            color: #555;
            margin: 20px 0;
        }}
        .transcript {{
            background: #fafafa;
            padding: 20px;
            border-radius: 4px;
            margin: 30px 0;
            max-height: 500px;
            overflow-y: auto;
        }}
        .transcript pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 0;
        }}
        .downloads {{
            margin: 30px 0;
            padding: 20px;
            background: #f0f7ff;
            border-radius: 4px;
        }}
        .downloads a {{
            display: inline-block;
            margin-right: 15px;
            padding: 8px 16px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 4px;
        }}
        .downloads a:hover {{
            background: #0056b3;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #999;
            font-size: 12px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="show-name">{episode.metadata.show_name}</div>
            <h1>{episode.metadata.title}</h1>
            <div class="date">{episode.metadata.date or 'Date not available'}</div>
        </div>
        
        {f'<div class="key-takeaway"><strong>Key Takeaway:</strong> {key_takeaway}</div>' if key_takeaway else ''}
        
        <div class="description">
            {description}
        </div>
        
        <div class="downloads">
            <strong>Download Transcripts:</strong><br><br>
            <a href="/assets/transcripts/{episode.episode_id}.txt" download>📄 Plain Text</a>
            <a href="/assets/transcripts/{episode.episode_id}.vtt" download>📝 WebVTT (Captions)</a>
            <a href="/meta/{episode.episode_id}.json" download>📊 Full Metadata (JSON)</a>
        </div>
        
        <h2>Transcript</h2>
        <div class="transcript">
            <pre>{transcript_data.get('text', 'Transcript not available')}</pre>
        </div>
        
        <div class="footer">
            Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Episode ID: {episode.episode_id}
        </div>
    </div>
</body>
</html>"""
        
        return html
