#!/usr/bin/env python3
"""
Redis Cluster Setup Script
==========================

This script provides a comprehensive Redis cluster setup solution with:
- Automatic SSH credential management
- System optimization (swap disable, kernel tuning)
- Enhanced RDB/AOF persistence configuration
- Comprehensive cluster health validation
- Post-deployment verification

Usage:
    python setup_redis_cluster.py --config configs/sample_cluster.yaml --action deploy
    python setup_redis_cluster.py --config configs/sample_cluster.yaml --action validate
    python setup_redis_cluster.py --config configs/sample_cluster.yaml --action pre-validate
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add the redis_deploy package to the path
sys.path.insert(0, str(Path(__file__).parent))

from redis_deploy.main import app
from redis_deploy.config import load_config
from redis_deploy.logging_setup import configure_logging
from rich import print as rprint
from rich.console import Console
from rich.table import Table


def print_configuration_summary(config_path: str) -> None:
    """Print a summary of the configuration"""
    console = Console()
    
    try:
        cfg = load_config(config_path)
        
        # Create configuration summary table
        table = Table(title="Redis Cluster Configuration Summary")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")
        
        table.add_row("Nodes", ", ".join(cfg.nodes))
        table.add_row("Redis Version", cfg.redis_version)
        table.add_row("Port Range", f"{cfg.ports.base}-{cfg.ports.base + cfg.ports.count_per_host - 1}")
        table.add_row("Instances per Host", str(cfg.ports.count_per_host))
        table.add_row("Masters", str(cfg.cluster.masters))
        table.add_row("Replicas per Master", str(cfg.cluster.replicas_per_master))
        table.add_row("Total Instances", str(cfg.total_instances()))
        table.add_row("Persistence Mode", cfg.persistence.mode)
        table.add_row("AOF Fsync", cfg.persistence.aof_fsync)
        table.add_row("Disable Swap", str(cfg.disable_swap))
        table.add_row("SSH User", cfg.ssh.user or "Not configured")
        table.add_row("SSH Port", str(cfg.ssh.port))
        
        console.print(table)
        
        # Warnings and recommendations
        console.print("\n[bold yellow]Configuration Checks:[/bold yellow]")
        
        if not cfg.ssh.user:
            console.print("⚠️  SSH user not configured. Set via config file or REDIS_DEPLOY_SSH_USER environment variable")
        
        if not cfg.ssh.password and not cfg.ssh.private_key:
            console.print("⚠️  No SSH authentication method configured. Set password or private_key in config")
        
        if cfg.total_instances() < 6:
            console.print("⚠️  Redis cluster requires at least 6 instances for high availability")
        
        if cfg.persistence.mode == "none":
            console.print("⚠️  Persistence disabled - data will be lost on restart")
        
        console.print("✅ Configuration loaded successfully")
        
    except Exception as e:
        console.print(f"[bold red]Configuration error: {e}[/bold red]")
        sys.exit(1)


def check_environment() -> None:
    """Check if required environment variables are set"""
    console = Console()
    
    console.print("[bold blue]Environment Check:[/bold blue]")
    
    env_vars = {
        "REDIS_DEPLOY_SSH_USER": "SSH username for Redis deployment",
        "REDIS_DEPLOY_SSH_PASSWORD": "SSH password (optional if using key)",
        "REDIS_DEPLOY_SSH_KEY": "SSH private key path (optional if using password)",
    }
    
    missing_vars = []
    for var, description in env_vars.items():
        value = os.environ.get(var)
        if value:
            if "PASSWORD" in var or "KEY" in var:
                console.print(f"✅ {var}: [dim]***[/dim]")
            else:
                console.print(f"✅ {var}: {value}")
        else:
            console.print(f"❌ {var}: Not set - {description}")
            missing_vars.append(var)
    
    if missing_vars:
        console.print(f"\n[yellow]Note: Missing environment variables can be configured in the YAML file[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="Redis Cluster Setup Script")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML configuration file")
    parser.add_argument("--action", choices=["deploy", "validate", "pre-validate", "rollback", "summary"], 
                       default="summary", help="Action to perform")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without executing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        configure_logging()
    
    # Check if config file exists
    if not os.path.exists(args.config):
        rprint(f"[bold red]Configuration file not found: {args.config}[/bold red]")
        sys.exit(1)
    
    # Handle different actions
    if args.action == "summary":
        rprint("[bold green]Redis Cluster Setup - Configuration Summary[/bold green]\n")
        check_environment()
        print_configuration_summary(args.config)
        
        rprint("\n[bold blue]Next Steps:[/bold blue]")
        rprint("1. Run pre-validation: python setup_redis_cluster.py --config {} --action pre-validate".format(args.config))
        rprint("2. Deploy cluster: python setup_redis_cluster.py --config {} --action deploy".format(args.config))
        rprint("3. Validate cluster: python setup_redis_cluster.py --config {} --action validate".format(args.config))
        
    elif args.action == "deploy":
        import typer
        from redis_deploy.main import deploy
        
        rprint("[bold green]Starting Redis cluster deployment...[/bold green]")
        try:
            deploy(config=args.config, dry_run=args.dry_run)
        except Exception as e:
            rprint(f"[bold red]Deployment failed: {e}[/bold red]")
            sys.exit(1)
            
    elif args.action == "validate":
        from redis_deploy.main import validate
        
        rprint("[bold blue]Validating Redis cluster...[/bold blue]")
        try:
            validate(config=args.config)
        except Exception as e:
            rprint(f"[bold red]Validation failed: {e}[/bold red]")
            sys.exit(1)
            
    elif args.action == "pre-validate":
        from redis_deploy.main import pre_validate
        
        rprint("[bold blue]Running pre-deployment validation...[/bold blue]")
        try:
            pre_validate(config=args.config)
        except Exception as e:
            rprint(f"[bold red]Pre-validation failed: {e}[/bold red]")
            sys.exit(1)
            
    elif args.action == "rollback":
        from redis_deploy.main import rollback
        
        rprint("[bold yellow]Rolling back Redis cluster...[/bold yellow]")
        try:
            rollback(config=args.config, dry_run=args.dry_run)
        except Exception as e:
            rprint(f"[bold red]Rollback failed: {e}[/bold red]")
            sys.exit(1)


if __name__ == "__main__":
    main()