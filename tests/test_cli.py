"""Test CLI commands."""

import pytest
from typer.testing import CliRunner
from src.ai_ewg.cli import app

runner = CliRunner()


def test_version():
    """Test version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ai-ewg" in result.stdout
    assert "version" in result.stdout


def test_help():
    """Test help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AI-powered video processing pipeline" in result.stdout


def test_discover_help():
    """Test discover command help."""
    result = runner.invoke(app, ["discover", "--help"])
    assert result.exit_code == 0
    assert "discover" in result.stdout.lower()


def test_db_init(tmp_path):
    """Test database initialization."""
    config_path = tmp_path / "config.yaml"
    db_path = tmp_path / 'data' / 'pipeline.db'
    config_path.write_text(f"""
sources:
  - path: {tmp_path / 'videos'}
    enabled: true
database:
  path: {db_path}
""")
    
    result = runner.invoke(app, ["--config", str(config_path), "db", "init"])
    assert result.exit_code == 0
    assert db_path.exists()


def test_db_status(tmp_path):
    """Test database status command."""
    config_path = tmp_path / "config.yaml"
    db_path = tmp_path / 'data' / 'pipeline.db'
    config_path.write_text(f"""
sources:
  - path: {tmp_path / 'videos'}
    enabled: true
database:
  path: {db_path}
""")
    
    # Initialize first
    runner.invoke(app, ["--config", str(config_path), "db", "init"])
    
    # Check status
    result = runner.invoke(app, ["--config", str(config_path), "db", "status"])
    assert result.exit_code == 0
    assert "Registry Statistics" in result.stdout or "Database" in result.stdout
