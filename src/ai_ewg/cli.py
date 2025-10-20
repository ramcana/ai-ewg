"""Main CLI entry point for ai-ewg pipeline."""

import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="ai-ewg",
    help="AI-powered video processing pipeline for educational content",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file (default: config/system.yaml)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """AI-EWG: Process videos through 10-stage pipeline."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config or Path("config/system.yaml")
    ctx.obj["verbose"] = verbose


@app.command()
def version():
    """Show version information."""
    from . import __version__
    console.print(f"[bold cyan]ai-ewg[/bold cyan] version [green]{__version__}[/green]")


# Discovery stage
@app.command()
def discover(
    ctx: typer.Context,
    source: Optional[Path] = typer.Option(None, "--source", "-s", help="Source directory to scan"),
    pattern: str = typer.Option("**/*.mp4", "--pattern", "-p", help="File pattern to match"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be discovered"),
):
    """Stage 1: Discover video files from configured sources."""
    from .stages.discovery import discover_videos
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        "[bold]Stage 1: Discovery[/bold]\nScanning for video files...",
        border_style="cyan"
    ))
    
    result = discover_videos(
        settings=settings,
        source=source,
        pattern=pattern,
        dry_run=dry_run,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Discovered {result['count']} videos")
    if result.get("new_count"):
        console.print(f"  [yellow]→[/yellow] {result['new_count']} new files")
    
    # n8n-friendly JSON output
    print(f'{{"stage": "discover", "success": true, "count": {result["count"]}}}')


@app.command()
def normalize(
    ctx: typer.Context,
    episode_id: Optional[str] = typer.Option(None, "--episode", "-e", help="Process specific episode"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-normalization"),
):
    """Stage 2: Normalize metadata and file paths."""
    from .stages.normalization import normalize_metadata
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        "[bold]Stage 2: Normalization[/bold]\nNormalizing metadata...",
        border_style="cyan"
    ))
    
    result = normalize_metadata(
        settings=settings,
        episode_id=episode_id,
        force=force,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Normalized {result['count']} episodes")
    print(f'{{"stage": "normalize", "success": true, "count": {result["count"]}}}')


@app.command()
def transcribe(
    ctx: typer.Context,
    episode_id: Optional[str] = typer.Option(None, "--episode", "-e", help="Process specific episode"),
    model: str = typer.Option("large-v3", "--model", "-m", help="Whisper model to use"),
    compute: str = typer.Option("fp16", "--compute", help="Compute type: fp16, int8"),
    device: str = typer.Option("auto", "--device", help="Device: auto, cuda, cpu"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-transcription"),
):
    """Stage 3: Transcribe audio using Faster-Whisper."""
    from .stages.transcription import transcribe_episodes
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        f"[bold]Stage 3: Transcription[/bold]\nModel: {model} | Compute: {compute}",
        border_style="cyan"
    ))
    
    result = transcribe_episodes(
        settings=settings,
        episode_id=episode_id,
        model=model,
        compute_type=compute,
        device=device,
        force=force,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Transcribed {result['count']} episodes")
    print(f'{{"stage": "transcribe", "success": true, "count": {result["count"]}}}')


@app.command()
def diarize(
    ctx: typer.Context,
    episode_id: Optional[str] = typer.Option(None, "--episode", "-e", help="Process specific episode"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-diarization"),
):
    """Stage 4: Perform speaker diarization."""
    from .stages.diarization import diarize_episodes
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        "[bold]Stage 4: Diarization[/bold]\nIdentifying speakers...",
        border_style="cyan"
    ))
    
    result = diarize_episodes(
        settings=settings,
        episode_id=episode_id,
        force=force,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Diarized {result['count']} episodes")
    print(f'{{"stage": "diarize", "success": true, "count": {result["count"]}}}')


# Enrichment commands
enrich_app = typer.Typer(help="Enrichment stage commands")
app.add_typer(enrich_app, name="enrich")


@enrich_app.command("entities")
def enrich_entities(
    ctx: typer.Context,
    episode_id: Optional[str] = typer.Option(None, "--episode", "-e", help="Process specific episode"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-extraction"),
):
    """Stage 5a: Extract named entities."""
    from .stages.enrichment import extract_entities
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        "[bold]Stage 5a: Entity Extraction[/bold]\nExtracting people, orgs, locations...",
        border_style="cyan"
    ))
    
    result = extract_entities(
        settings=settings,
        episode_id=episode_id,
        force=force,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Extracted entities from {result['count']} episodes")
    print(f'{{"stage": "enrich_entities", "success": true, "count": {result["count"]}}}')


@enrich_app.command("disambiguate")
def enrich_disambiguate(
    ctx: typer.Context,
    episode_id: Optional[str] = typer.Option(None, "--episode", "-e", help="Process specific episode"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-disambiguation"),
):
    """Stage 5b: Disambiguate entities against knowledge bases."""
    from .stages.enrichment import disambiguate_entities
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        "[bold]Stage 5b: Entity Disambiguation[/bold]\nMatching to Wikidata...",
        border_style="cyan"
    ))
    
    result = disambiguate_entities(
        settings=settings,
        episode_id=episode_id,
        force=force,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Disambiguated {result['count']} episodes")
    print(f'{{"stage": "enrich_disambiguate", "success": true, "count": {result["count"]}}}')


@enrich_app.command("score")
def enrich_score(
    ctx: typer.Context,
    episode_id: Optional[str] = typer.Option(None, "--episode", "-e", help="Process specific episode"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-scoring"),
):
    """Stage 5c: Score and rank entities."""
    from .stages.enrichment import score_entities
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        "[bold]Stage 5c: Entity Scoring[/bold]\nRanking by relevance...",
        border_style="cyan"
    ))
    
    result = score_entities(
        settings=settings,
        episode_id=episode_id,
        force=force,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Scored entities in {result['count']} episodes")
    print(f'{{"stage": "enrich_score", "success": true, "count": {result["count"]}}}')


# Web generation commands
web_app = typer.Typer(help="Web artifact generation commands")
app.add_typer(web_app, name="web")


@web_app.command("build")
def web_build(
    ctx: typer.Context,
    episode_id: Optional[str] = typer.Option(None, "--episode", "-e", help="Build specific episode"),
    force: bool = typer.Option(False, "--force", "-f", help="Force rebuild"),
):
    """Stage 9: Build HTML pages with JSON-LD."""
    from .stages.web_generation import build_web_artifacts
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        "[bold]Stage 9: Web Generation[/bold]\nBuilding HTML pages...",
        border_style="cyan"
    ))
    
    result = build_web_artifacts(
        settings=settings,
        episode_id=episode_id,
        force=force,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Built {result['count']} pages")
    print(f'{{"stage": "web_build", "success": true, "count": {result["count"]}}}')


# Index generation commands
index_app = typer.Typer(help="Index generation commands")
app.add_typer(index_app, name="index")


@index_app.command("build")
def index_build(
    ctx: typer.Context,
    kind: str = typer.Option("all", "--kind", "-k", help="Index type: all, shows, hosts, sitemap, rss"),
):
    """Stage 10: Build indices, sitemaps, and feeds."""
    from .stages.indexing import build_indices
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print(Panel.fit(
        f"[bold]Stage 10: Indexing[/bold]\nBuilding {kind} indices...",
        border_style="cyan"
    ))
    
    result = build_indices(
        settings=settings,
        kind=kind,
        verbose=ctx.obj["verbose"]
    )
    
    console.print(f"\n[green]✓[/green] Built {result['count']} indices")
    print(f'{{"stage": "index_build", "success": true, "count": {result["count"]}}}')


# Database commands
db_app = typer.Typer(help="Registry database commands")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init(ctx: typer.Context):
    """Initialize the registry database."""
    from .core.registry import init_database
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print("[cyan]Initializing registry database...[/cyan]")
    init_database(settings)
    console.print("[green]✓[/green] Database initialized")


@db_app.command("status")
def db_status(ctx: typer.Context):
    """Show registry database statistics."""
    from .core.registry import get_registry_stats
    from .core.settings import get_settings
    from rich.table import Table
    
    settings = get_settings(ctx.obj["config"])
    stats = get_registry_stats(settings)
    
    table = Table(title="Registry Statistics")
    table.add_column("Entity", style="cyan")
    table.add_column("Count", justify="right", style="green")
    
    for entity, count in stats.items():
        table.add_row(entity.title(), str(count))
    
    console.print(table)


@db_app.command("migrate")
def db_migrate(ctx: typer.Context):
    """Run database migrations."""
    from .core.registry import run_migrations
    from .core.settings import get_settings
    
    settings = get_settings(ctx.obj["config"])
    
    console.print("[cyan]Running migrations...[/cyan]")
    result = run_migrations(settings)
    console.print(f"[green]✓[/green] Applied {result['count']} migrations")


def main_cli():
    """Entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_cli()
