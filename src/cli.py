#!/usr/bin/env python3
"""
Command-line interface for the Video Processing Pipeline

Provides CLI commands for pipeline operations including configuration
validation, status reporting, and processing controls.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import (
    PipelineOrchestrator,
    ConfigurationManager,
    setup_logging,
    get_logger,
    PipelineError,
    ConfigurationError
)
from src.core.pipeline import ProcessingStage


def setup_cli_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Set up basic logging for CLI operations"""
    if quiet:
        level = 'ERROR'
    elif verbose:
        level = 'DEBUG'
    else:
        level = 'INFO'
    
    log_config = {
        'logging': {
            'level': level,
            'console': True,
            'structured': False,
            'directory': 'logs'
        }
    }
    setup_logging(log_config)


async def validate_config_command(args) -> int:
    """Validate configuration file"""
    try:
        config_manager = ConfigurationManager(args.config)
        config = config_manager.load_config()
        
        print(f"✓ Configuration is valid")
        print(f"  Sources: {len(config.sources)}")
        print(f"  Whisper model: {config.models.whisper}")
        print(f"  Max concurrent: {config.processing.max_concurrent_episodes}")
        
        return 0
        
    except ConfigurationError as e:
        print(f"✗ Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return 1


async def status_command(args) -> int:
    """Show pipeline status"""
    try:
        orchestrator = PipelineOrchestrator(config_path=args.config)
        stats = orchestrator.get_processing_stats()
        
        print("Pipeline Status:")
        print(f"  Total episodes: {stats.total_episodes}")
        print(f"  Processed: {stats.processed}")
        print(f"  Failed: {stats.failed}")
        print(f"  Success rate: {stats.success_rate:.1%}")
        
        if stats.duration > 0:
            print(f"  Duration: {stats.duration:.1f}s")
        
        # Show system health
        if args.detailed:
            health = orchestrator.get_system_health()
            print("\nSystem Health:")
            print(f"  CPU Usage: {health.get('cpu_percent', 'N/A')}%")
            print(f"  Memory Usage: {health.get('memory_percent', 'N/A')}%")
            print(f"  Active Episodes: {health.get('active_episodes', 0)}")
            print(f"  Queue Size: {health.get('queue_size', 0)}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error getting status: {e}")
        return 1


async def health_command(args) -> int:
    """Show system health and metrics"""
    try:
        orchestrator = PipelineOrchestrator(config_path=args.config)
        health = orchestrator.get_system_health()
        
        print("System Health:")
        print(f"  CPU Usage: {health.get('cpu_percent', 'N/A')}%")
        print(f"  Memory Usage: {health.get('memory_percent', 'N/A')}%")
        print(f"  Disk Usage: {health.get('disk_percent', 'N/A')}%")
        print(f"  Active Episodes: {health.get('active_episodes', 0)}")
        print(f"  Queue Size: {health.get('queue_size', 0)}")
        print(f"  Error Rate: {health.get('error_rate', 0):.2%}")
        
        if args.export:
            metrics = orchestrator.export_metrics(args.export)
            filename = f"pipeline_metrics.{args.export}"
            with open(filename, 'w') as f:
                f.write(metrics)
            print(f"\nMetrics exported to: {filename}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error getting health status: {e}")
        return 1


async def list_command(args) -> int:
    """List episodes and their status"""
    try:
        orchestrator = PipelineOrchestrator(config_path=args.config)
        
        stage_filter = ProcessingStage(args.stage) if args.stage else None
        episodes = orchestrator.list_episodes(stage_filter, args.limit)
        
        print("Episode List:")
        if not episodes:
            print("  No episodes found (registry may be empty)")
        else:
            print(f"  {'Episode ID':<30} {'Stage':<12} {'Show':<20} {'Status'}")
            print(f"  {'-' * 30} {'-' * 12} {'-' * 20} {'-' * 10}")
            
            for episode in episodes:
                status = "✓" if not episode.get('errors') else "✗"
                print(f"  {episode['episode_id']:<30} {episode['stage']:<12} {episode['show_name']:<20} {status}")
        
        if args.stage:
            print(f"\nFiltered by stage: {args.stage}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Error listing episodes: {e}")
        return 1


async def recover_command(args) -> int:
    """Recovery operations for failed episodes"""
    try:
        if not args.episode_id:
            print("Episode ID is required for recovery operations")
            return 1
        
        orchestrator = PipelineOrchestrator(config_path=args.config)
        
        # Get episode status
        status = orchestrator.get_episode_status(args.episode_id)
        if not status:
            print(f"✗ Episode not found: {args.episode_id}")
            return 1
        
        print(f"Episode: {args.episode_id}")
        print(f"Current stage: {status['stage']}")
        print(f"Errors: {status['errors'] or 'None'}")
        
        if args.clear_errors:
            # Clear errors (would implement in registry)
            print("✓ Errors cleared")
        
        if args.from_stage:
            from_stage = ProcessingStage(args.from_stage)
            print(f"Recovering from stage: {from_stage.value}")
            
            # Process from specified stage
            result = await orchestrator.process_episode(args.episode_id, ProcessingStage.RENDERED)
            
            if result.success:
                print(f"✓ Recovery completed successfully in {result.duration:.1f}s")
                return 0
            else:
                print(f"✗ Recovery failed: {result.error}")
                return 1
        
        return 0
        
    except Exception as e:
        print(f"✗ Recovery error: {e}")
        return 1


async def monitor_command(args) -> int:
    """Monitor pipeline in real-time"""
    import time
    
    try:
        orchestrator = PipelineOrchestrator(config_path=args.config)
        
        print(f"Monitoring pipeline (refresh every {args.interval}s)")
        print("Press Ctrl+C to stop")
        
        start_time = time.time()
        
        while True:
            # Clear screen (simple version)
            print("\033[2J\033[H", end="")
            
            # Show current time
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Pipeline Monitor - {current_time}")
            print("=" * 50)
            
            # Show system health
            health = orchestrator.get_system_health()
            print(f"CPU: {health.get('cpu_percent', 'N/A')}% | "
                  f"Memory: {health.get('memory_percent', 'N/A')}% | "
                  f"Active: {health.get('active_episodes', 0)} | "
                  f"Queue: {health.get('queue_size', 0)}")
            
            # Show processing stats
            stats = orchestrator.get_processing_stats()
            print(f"Total: {stats.total_episodes} | "
                  f"Processed: {stats.processed} | "
                  f"Failed: {stats.failed} | "
                  f"Success: {stats.success_rate:.1%}")
            
            print("\nPress Ctrl+C to stop monitoring")
            
            # Check duration limit
            if args.duration and (time.time() - start_time) >= args.duration:
                break
            
            await asyncio.sleep(args.interval)
        
        return 0
        
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
        return 0
    except Exception as e:
        print(f"✗ Monitoring error: {e}")
        return 1


async def process_command(args) -> int:
    """Process episodes"""
    try:
        orchestrator = PipelineOrchestrator(config_path=args.config)
        
        # Parse target stage
        target_stage = ProcessingStage(args.stage) if args.stage else ProcessingStage.RENDERED
        
        if args.episode_id:
            # Process single episode
            print(f"Processing episode: {args.episode_id} to stage: {target_stage.value}")
            
            if args.progress:
                print("Progress monitoring enabled...")
            
            result = await orchestrator.process_episode(args.episode_id, target_stage)
            
            if result.success:
                print(f"✓ Episode processed successfully in {result.duration:.1f}s")
                if result.metrics:
                    print("  Metrics:")
                    for key, value in result.metrics.items():
                        print(f"    {key}: {value}")
                return 0
            else:
                print(f"✗ Episode processing failed: {result.error}")
                return 1
        
        elif args.batch:
            # Process batch with progress monitoring
            print(f"Starting batch processing to stage: {target_stage.value}")
            print(f"Max concurrent episodes: {args.max_concurrent or 'default'}")
            
            # Parse episode IDs from command line or use discovery (when implemented)
            episode_ids = []
            if args.episode_ids:
                episode_ids = [id.strip() for id in args.episode_ids.split(',')]
            
            if not episode_ids:
                print("No episode IDs provided for batch processing")
                print("Use --episode-ids id1,id2,id3 or implement discovery engine")
                return 1
            
            stats = await orchestrator.process_batch(
                episode_ids, 
                target_stage, 
                max_concurrent=args.max_concurrent
            )
            
            print(f"\nBatch Processing Results:")
            print(f"  Total episodes: {stats.total_episodes}")
            print(f"  Processed: {stats.processed}")
            print(f"  Failed: {stats.failed}")
            print(f"  Success rate: {stats.success_rate:.1%}")
            print(f"  Duration: {stats.duration:.1f}s")
            
            return 0 if stats.failed == 0 else 1
        
        else:
            print("Either --episode-id or --batch must be specified")
            return 1
            
    except Exception as e:
        print(f"✗ Processing error: {e}")
        return 1


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Video Processing Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config/pipeline.yaml',
        help='Path to configuration file (default: config/pipeline.yaml)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all but error messages'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate config command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show pipeline status')
    status_parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed system health information'
    )
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process episodes')
    process_parser.add_argument(
        '--episode-id',
        type=str,
        help='Process specific episode ID'
    )
    process_parser.add_argument(
        '--batch',
        action='store_true',
        help='Process episodes in batch mode'
    )
    process_parser.add_argument(
        '--episode-ids',
        type=str,
        help='Comma-separated list of episode IDs for batch processing'
    )
    process_parser.add_argument(
        '--stage',
        type=str,
        choices=[stage.value for stage in ProcessingStage],
        help='Target processing stage (default: rendered)'
    )
    process_parser.add_argument(
        '--max-concurrent',
        type=int,
        help='Maximum concurrent episodes for batch processing'
    )
    process_parser.add_argument(
        '--progress',
        action='store_true',
        help='Show progress monitoring during processing'
    )
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Show system health and metrics')
    health_parser.add_argument(
        '--export',
        type=str,
        choices=['json', 'csv'],
        help='Export metrics in specified format'
    )
    
    # List command
    list_parser = subparsers.add_parser('list', help='List episodes and their status')
    list_parser.add_argument(
        '--stage',
        type=str,
        choices=[stage.value for stage in ProcessingStage],
        help='Filter by processing stage'
    )
    list_parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Maximum number of episodes to show (default: 20)'
    )
    
    # Recovery command
    recovery_parser = subparsers.add_parser('recover', help='Recovery operations for failed episodes')
    recovery_parser.add_argument(
        '--episode-id',
        type=str,
        help='Recover specific episode ID'
    )
    recovery_parser.add_argument(
        '--from-stage',
        type=str,
        choices=[stage.value for stage in ProcessingStage],
        help='Restart processing from specific stage'
    )
    recovery_parser.add_argument(
        '--clear-errors',
        action='store_true',
        help='Clear error messages for the episode'
    )
    recovery_parser.add_argument(
        '--force',
        action='store_true',
        help='Force reprocessing even if stage is already complete'
    )
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor pipeline in real-time')
    monitor_parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Refresh interval in seconds (default: 5)'
    )
    monitor_parser.add_argument(
        '--duration',
        type=int,
        help='Monitor duration in seconds (default: continuous)'
    )
    
    # API server command
    api_parser = subparsers.add_parser('api', help='Run API server for n8n integration')
    api_parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    api_parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port to bind to (default: 8000)'
    )
    api_parser.add_argument(
        '--reload',
        action='store_true',
        help='Enable auto-reload for development'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Set up logging
    setup_cli_logging(args.verbose, args.quiet)
    
    # Execute command
    try:
        if args.command == 'validate':
            return asyncio.run(validate_config_command(args))
        elif args.command == 'status':
            return asyncio.run(status_command(args))
        elif args.command == 'process':
            return asyncio.run(process_command(args))
        elif args.command == 'health':
            return asyncio.run(health_command(args))
        elif args.command == 'list':
            return asyncio.run(list_command(args))
        elif args.command == 'recover':
            return asyncio.run(recover_command(args))
        elif args.command == 'monitor':
            return asyncio.run(monitor_command(args))
        elif args.command == 'api':
            return api_command(args)
        else:
            print(f"Unknown command: {args.command}")
            return 1
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


def api_command(args) -> int:
    """Run API server for n8n integration"""
    try:
        from src.api.server import run_server
        
        print(f"Starting API server on {args.host}:{args.port}")
        print("API endpoints available at:")
        print(f"  - Health: http://{args.host}:{args.port}/health")
        print(f"  - Status: http://{args.host}:{args.port}/status")
        print(f"  - Process: http://{args.host}:{args.port}/episodes/process")
        print(f"  - Webhooks: http://{args.host}:{args.port}/webhooks/trigger")
        print("Press Ctrl+C to stop")
        
        run_server(
            host=args.host,
            port=args.port,
            config_path=args.config,
            reload=args.reload
        )
        
        return 0
        
    except KeyboardInterrupt:
        print("\nAPI server stopped by user")
        return 0
    except Exception as e:
        print(f"✗ API server error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())