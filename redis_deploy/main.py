from __future__ import annotations

import logging
from typing import Optional

import typer
from rich import print as rprint

from .cluster import create_cluster
from .config import load_config, TopologyConfig
from .install import disable_swap, install_redis_from_source
from .logging_setup import configure_logging
from .placement import enumerate_instances, assign_roles
from .redis_instance import install_instance
from .rollback import rollback_host
from .ssh import SSH, SSHCredentials
from .validate import validate_cluster
from .observability import setup_exporters_on_host, validate_exporters, provision_grafana

app = typer.Typer(add_completion=False)
LOGGER = logging.getLogger(__name__)


def _ssh_for_host(cfg: TopologyConfig, host: str, dry_run: bool = False) -> SSH:
	creds = SSHCredentials(
		host=host,
		user=cfg.ssh.user,
		port=cfg.ssh.port,
		password=cfg.ssh.password,
		private_key=cfg.ssh.private_key,
	)
	return SSH(creds, dry_run=dry_run)


@app.command("deploy")
def deploy(config: str = typer.Option(..., "--config", "-c", help="Path to YAML config"), dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without executing")) -> None:
	"""
	Deploy Redis across nodes and form a cluster based on YAML config.
	"""
	configure_logging()
	cfg = load_config(config)
	rprint("[bold green]Loaded config[/bold green]")
	masters, replicas = assign_roles(cfg)
	rprint(f"Planned masters: {[f'{m.host}:{m.port}' for m in masters]}")
	for m, reps in replicas.items():
		rprint(f"Master {m.host}:{m.port} replicas: {[f'{r.host}:{r.port}' for r in reps]}")

	# Node provisioning: install Redis and instances
	for host in cfg.nodes:
		with _ssh_for_host(cfg, host, dry_run=dry_run) as ssh:
			if cfg.disable_swap:
				disable_swap(ssh)
			install_redis_from_source(ssh, cfg.redis_version, cfg.paths.install_prefix)
			for i in range(cfg.ports.count_per_host):
				port = cfg.ports.base + i
				install_instance(ssh, cfg, port)
			setup_exporters_on_host(ssh, cfg)
			validate_exporters(ssh, cfg)

	if cfg.cluster.create:
		create_cluster(cfg, dry_run=dry_run)
		validate_cluster(cfg, dry_run=dry_run)
	provision_grafana(cfg)
	rprint("[bold green]Deployment complete[/bold green]")


@app.command("validate")
def validate(config: str = typer.Option(..., "--config", "-c")) -> None:
	configure_logging()
	cfg = load_config(config)
	validate_cluster(cfg, dry_run=False)
	rprint("[bold green]Validation OK[/bold green]")


@app.command("rollback")
def rollback(config: str = typer.Option(..., "--config", "-c"), dry_run: bool = typer.Option(False, "--dry-run")) -> None:
	configure_logging()
	cfg = load_config(config)
	for host in cfg.nodes:
		ports = [cfg.ports.base + i for i in range(cfg.ports.count_per_host)]
		rollback_host(cfg, host, ports, dry_run=dry_run)
	rprint("[bold yellow]Rollback executed[/bold yellow]")


def main() -> None:
	app()


if __name__ == "__main__":
	main()


